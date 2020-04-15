#
# Copyright (c) 2020, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import dask.array as da
import dask.delayed
from dask.distributed import default_client, get_worker
import numpy as np
import cupy as cp
from cuml.utils import rmm_cupy_ary
from cuml.dask.common.part_utils import _extract_partitions
from cuml.datasets.regression import make_regression as sg_make_regression
from cuml.utils import with_cupy_rmm


def create_rs_generator(random_state):
    if hasattr(random_state, '__module__'):
        rs_type = random_state.__module__ + '.' + type(random_state).__name__
    else:
        rs_type = type(random_state).__name__

    rs = None
    if rs_type == "NoneType" or rs_type == "int":
        rs = da.random.RandomState(seed=random_state,
                                   RandomState=cp.random.RandomState)
    elif rs_type == "cupy.random.generator.RandomState":
        rs = da.random.RandomState(RandomState=random_state)
    elif rs_type == "dask.array.random.RandomState":
        rs = random_state
    else:
        raise ValueError('random_state type must be int, CuPy RandomState \
                          or Dask RandomState')
    return rs


def _f_order_standard_normal(nrows, ncols, dtype, seed):
    local_rs = cp.random.RandomState(seed=seed)
    x = local_rs.standard_normal(nrows * ncols, dtype=dtype)
    x = x.reshape((nrows, ncols), order='F')
    return x


def f_order_standard_normal(client, rs, nrows, ncols, chunksizes, dtype):
    chunk_seeds = rs.permutation(len(chunksizes))
    chunks = [client.submit(_f_order_standard_normal, chunksize, ncols, dtype,
                            chunk_seeds[idx])
              for idx, chunksize in enumerate(chunksizes)]

    chunks_dela = [da.from_delayed(dask.delayed(chunk),
                                   shape=(chunksizes[idx], ncols),
                                   meta=cp.zeros((1)), dtype=dtype)
                   for idx, chunk in enumerate(chunks)]
    return da.concatenate(chunks_dela, axis=0)


def get_X(t):
    return t[0]


def get_labels(t):
    return t[1]


def _f_order_shuffle(X, y, n_samples_per_part, seed, features_indices):
    local_rs = cp.random.RandomState(seed=seed)
    samples_indices = local_rs.permutation(n_samples_per_part)

    X[...] = X[samples_indices, :]
    X[...] = X[:, features_indices]

    y[...] = y[samples_indices, :]
    return X, y


def f_order_shuffle(client, rs, X, y, n_parts, n_samples_per_part,
                    n_features, features_indices, n_targets, dtype):
    X_parts = client.sync(_extract_partitions, X)
    y_parts = client.sync(_extract_partitions, y)

    chunk_seeds = rs.permutation(n_parts)

    shuffled = [client.submit(_f_order_shuffle, X_part, y_parts[idx][1],
                                n_samples_per_part,
                                chunk_seeds[idx], features_indices,
                                workers=[w])
                    for idx, (w, X_part) in enumerate(X_parts)]

    X_shuffled = [client.submit(get_X, f, pure=False)
                  for idx, f in enumerate(shuffled)]
    y_shuffled = [client.submit(get_labels, f, pure=False)
                  for idx, f in enumerate(shuffled)]

    X_dela = [da.from_delayed(dask.delayed(Xs),
                              shape=(n_samples_per_part, n_features),
                              meta=cp.zeros((1)),
                              dtype=dtype)
              for Xs in X_shuffled]
    
    y_dela = [da.from_delayed(dask.delayed(ys),
                              shape=(n_samples_per_part, n_targets),
                              meta=cp.zeros((1)),
                              dtype=dtype)
              for ys in y_shuffled]

    return da.concatenate(X_dela, axis=0), da.concatenate(y_dela, axis=0)


def make_low_rank_matrix(client=None, n_samples=100, n_features=100,
                         effective_rank=10, tail_strength=0.5,
                         random_state=None, n_parts=1,
                         n_samples_per_part=None, dtype='float32', order='F'):
    """ Generate a mostly low rank matrix with bell-shaped singular values

    Parameters
    ----------
    n_samples : int, optional (default=100)
        The number of samples.
    n_features : int, optional (default=100)
        The number of features.
    effective_rank : int, optional (default=10)
        The approximate number of singular vectors required to explain most of
        the data by linear combinations.
    tail_strength : float between 0.0 and 1.0, optional (default=0.5)
        The relative importance of the fat noisy tail of the singular values
        profile.
    random_state : int, CuPy RandomState instance, Dask RandomState instance
                   or None (default)
        Determines random number generation for dataset creation. Pass an int
        for reproducible output across multiple function calls.
    n_parts : int, optional (default=1)
        The number of parts of work.
    dtype: str, optional (default='float32')
        dtype of generated data

    Returns
    -------
    X : Dask-CuPy array of shape [n_samples, n_features]
        The matrix.
    """

    client = default_client() if client is None else client

    rs = create_rs_generator(random_state)
    n = min(n_samples, n_features)

    def generate_chunks_for_qr(total_size, min_size, n_parts):

        n_total_per_part = max(1, int(total_size / n_parts))
        if n_total_per_part > min_size:
            min_size = n_total_per_part

        n_partitions = int(max(1, total_size / min_size))
        rest = total_size % (n_partitions * min_size)
        chunks_list = [min_size for i in range(n_partitions-1)]
        chunks_list.append(min_size + rest)
        return tuple(chunks_list)

    # Random (ortho normal) vectors
    m1 = rs.standard_normal((n_samples, n),
                            chunks=(generate_chunks_for_qr(n_samples,
                                                        n, n_parts), -1),
                            dtype=dtype)
    u, _ = da.linalg.qr(m1)

    m2 = rs.standard_normal((n, n_features),
                            chunks=(-1, generate_chunks_for_qr(n_features,
                                                               n, n_parts)),
                            dtype=dtype)
    v, _ = da.linalg.qr(m2)

    # For final multiplication
    if n_samples_per_part is None:
        n_samples_per_part = max(1, int(n_samples / n_parts))
    u = u.rechunk({0: n_samples_per_part, 1: -1})
    v = v.rechunk({0: n_samples_per_part, 1: -1})

    # Index of the singular values
    sing_ind = rmm_cupy_ary(cp.arange, n, dtype=cp.float64)

    # Build the singular profile by assembling signal and noise components
    tmp = sing_ind / effective_rank
    low_rank = ((1 - tail_strength) * rmm_cupy_ary(cp.exp, -1.0 * tmp ** 2))
    tail = tail_strength * rmm_cupy_ary(cp.exp, -0.1 * tmp)
    local_s = low_rank + tail
    s = da.from_array(local_s,
                      chunks=(int(n_samples_per_part),))

    u *= s
    return da.dot(u, v)


@with_cupy_rmm
def make_regression(n_samples=100, n_features=100, n_informative=10,
                    n_targets=1, bias=0.0, effective_rank=None,
                    tail_strength=0.5, noise=0.0, shuffle=False, coef=False,
                    random_state=None, n_parts=1, n_samples_per_part=None,
                    order='F', dtype='float32', client=None,
                    use_full_low_rank=True):
    """Generate a random regression problem.
    The input set can either be well conditioned (by default) or have a low
    rank-fat tail singular profile.

    The output is generated by applying a (potentially biased) random linear
    regression model with "n_informative" nonzero regressors to the previously
    generated input and some gaussian centered noise with some adjustable
    scale.

    Parameters
    ----------
    n_samples : int, optional (default=100)
        The number of samples.
    n_features : int, optional (default=100)
        The number of features.
    n_informative : int, optional (default=10)
        The number of informative features, i.e., the number of features used
        to build the linear model used to generate the output.
    n_targets : int, optional (default=1)
        The number of regression targets, i.e., the dimension of the y output
        vector associated with a sample. By default, the output is a scalar.
    bias : float, optional (default=0.0)
        The bias term in the underlying linear model.
    effective_rank : int or None, optional (default=None)
        if not None:
            The approximate number of singular vectors required to explain most
            of the input data by linear combinations. Using this kind of
            singular spectrum in the input allows the generator to reproduce
            the correlations often observed in practice.
        if None:
            The input set is well conditioned, centered and gaussian with
            unit variance.
    tail_strength : float between 0.0 and 1.0, optional (default=0.5)
        The relative importance of the fat noisy tail of the singular values
        profile if "effective_rank" is not None.
    noise : float, optional (default=0.0)
        The standard deviation of the gaussian noise applied to the output.
    shuffle : boolean, optional (default=False)
        Shuffle the samples and the features.
    coef : boolean, optional (default=False)
        If True, the coefficients of the underlying linear model are returned.
    random_state : int, CuPy RandomState instance, Dask RandomState instance
                   or None (default)
        Determines random number generation for dataset creation. Pass an int
        for reproducible output across multiple function calls.
    n_parts : int, optional (default=1)
        The number of parts of work.
    order : str, optional (default='F')
        Row-major or Col-major
    dtype: str, optional (default='float32')
        dtype of generated data
    use_full_low_rank : boolean (default=True)
        Whether to use the entire dataset to generate the low rank matrix.
        If False, it uses the first chunk

    Returns
    -------
    X : Dask-CuPy array of shape [n_samples, n_features]
        The input samples.
    y : Dask-CuPy array of shape [n_samples] or [n_samples, n_targets]
        The output values.
    coef : Dask-CuPy array of shape [n_features]
           or [n_features, n_targets], optional
        The coefficient of the underlying linear model. It is returned only if
        coef is True.
    """

    client = default_client() if client is None else client

    n_informative = min(n_features, n_informative)
    rs = create_rs_generator(random_state)

    if n_samples_per_part is None:
        n_samples_per_part = max(1, int(n_samples / n_parts))

    if (effective_rank is None) or (effective_rank and not use_full_low_rank):
        # Randomly generate a well conditioned input set
        if order == 'F':
            X = f_order_standard_normal(client, rs, n_samples, n_features,
                                        [n_samples_per_part] * n_parts, dtype)
        elif order == 'C':
            X = rs.standard_normal((n_samples, n_features),
                                chunks=(n_samples_per_part, (n_informative,
                                                                n_features -
                                                                n_informative)),
                                dtype=dtype)

    else:
        # Randomly generate a low rank, fat tail input set
        X = make_low_rank_matrix(client=client, 
                                n_samples=n_samples,
                                n_features=n_features,
                                effective_rank=effective_rank,
                                tail_strength=tail_strength,
                                random_state=rs,
                                n_parts=n_parts,
                                dtype=dtype,
                                order=order)
        X = X.rechunk({0: n_samples_per_part,
                    1: (n_informative, n_features-n_informative)})

    # Generate a ground truth model with only n_informative features being non
    # zeros (the other features are not correlated to y and should be ignored
    # by a sparsifying regularizers such as L1 or elastic net)
    if effective_rank and not use_full_low_rank:
        _, _, coef_ = sg_make_regression(n_samples=n_samples_per_part,
                                        n_features=n_features,
                                        n_informative=n_informative,
                                        n_targets=n_targets,
                                        bias=bias,
                                        effective_rank=effective_rank,
                                        tail_strength=tail_strength,
                                        noise=noise,
                                        shuffle=shuffle,
                                        coef=True,
                                        random_state=random_state,
                                        dtype='double')
        coef_ = cp.array(coef_, dtype=dtype)
        ground_truth = da.from_array(coef_, chunks=(n_samples_per_part, -1))
        y = da.dot(X, ground_truth) + bias
    else:
        ground_truth = 100.0 * rs.standard_normal((n_informative, n_targets),
                                                chunks=(n_samples_per_part, -1),
                                                dtype=dtype)

        y = da.dot(X[:, :n_informative], ground_truth) + bias
    X = X.rechunk((None, -1))

    if n_informative != n_features and (effective_rank is None or use_full_low_rank):
        zeroes = 0.0 * rs.standard_normal((n_features -
                                           n_informative,
                                           n_targets), dtype=dtype)
        ground_truth = da.concatenate([ground_truth, zeroes], axis=0)
        ground_truth = ground_truth.rechunk(-1)

    # Add noise
    if noise > 0.0:
        y += rs.normal(scale=noise, size=y.shape, dtype=dtype)

    # Randomly permute samples and features
    if shuffle:
        features_indices = np.random.permutation(n_features)
        if order == 'F':
            X, y = f_order_shuffle(client, rs, X, y, n_parts,
                                   n_samples_per_part,
                                   n_features, features_indices,
                                   n_targets, dtype)
            
        elif order == 'C':
            samples_indices = np.random.permutation(n_samples)

            X = X[samples_indices, :]
            y = y[samples_indices, :]

            X = X[:, features_indices]
        ground_truth = ground_truth[features_indices, :]

    y = da.squeeze(y)

    if coef:
        ground_truth = da.squeeze(ground_truth)
        return X, y, ground_truth

    else:
        return X, y
