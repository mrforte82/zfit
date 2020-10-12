"""Example test for a pdf or function"""
#  Copyright (c) 2020 zfit

import numpy as np
import pytest
import scipy.stats
import tensorflow as tf

import zfit.models.convolution
from zfit import z
# noinspection PyUnresolvedReferences
from zfit.core.testing import setup_function, teardown_function, tester

param1_true = 0.3
param2_true = 1.2


class FFTConvV1NoSampling(zfit.pdf.FFTConvV1):

    @zfit.supports()
    def _sample(self, n, limits):
        raise zfit.exception.SpecificFunctionNotImplementedError


@pytest.mark.parametrize('interpolation', (
    'linear',
    'spline',
    'spline:5',
    'spline:3'
))
def test_conv_simple(interpolation):
    n_points = 2432
    obs = zfit.Space("obs1", limits=(-5, 5))
    param1 = zfit.Parameter('param1', -3)
    param2 = zfit.Parameter('param2', 0.3)
    gauss = zfit.pdf.Gauss(0., param2, obs=obs)
    func1 = zfit.pdf.Uniform(param1, param2, obs=obs)
    func2 = zfit.pdf.Uniform(-1.2, -1, obs=obs)
    func = zfit.pdf.SumPDF([func1, func2], 0.5)
    conv = zfit.pdf.FFTConvV1(func=func, kernel=gauss, n=100, interpolation=interpolation)
    if interpolation == 'spline:5':
        assert conv._spline_order == 5
    elif interpolation == 'spline:3':
        assert conv._spline_order == 3

    x = tf.linspace(-5., 5., n_points)
    probs = conv.pdf(x=x)

    # true convolution
    true_conv = true_conv_np(func, gauss, n_points, obs, x)

    integral = conv.integrate(limits=obs)
    probs_np = probs.numpy()
    np.testing.assert_allclose(probs, true_conv, rtol=0.2, atol=0.1)

    assert pytest.approx(1, rel=1e-3) == integral.numpy()
    assert len(probs_np) == n_points

    #
    # import matplotlib.pyplot as plt
    # plt.figure()
    # plt.plot(x, probs_np, label='zfit')
    # plt.plot(x, true_conv, label='numpy')
    # plt.legend()
    # plt.title(interpolation)
    # plt.show()


def test_onedim_sampling():
    obs = zfit.Space("obs1", limits=(-5, 5))
    param1 = zfit.Parameter('param1', -3)
    param2 = zfit.Parameter('param2', 0.3)
    gauss = zfit.pdf.Gauss(0., param2, obs=obs)
    func1 = zfit.pdf.Uniform(param1, param2, obs=obs)
    func2 = zfit.pdf.Uniform(-1.2, -1, obs=obs)
    func = zfit.pdf.SumPDF([func1, func2], 0.5)
    conv = zfit.pdf.FFTConvV1(func=func, kernel=gauss)

    conv_nosample = FFTConvV1NoSampling(func=func, kernel=gauss, n=300)
    npoints_sample = 10000
    sample = conv.sample(npoints_sample)
    sample_nosample = conv_nosample.sample(npoints_sample)
    x = z.unstack_x(sample)
    xns = z.unstack_x(sample_nosample)
    assert scipy.stats.ks_2samp(x, xns).pvalue > 0.001

    # import matplotlib.pyplot as plt
    # plt.figure()
    # plt.hist(x, bins=50, label='custom')
    # plt.hist(xns, bins=50, label='fallback')
    # plt.legend()
    # plt.show()


def true_conv_np(func, gauss1, n_points, obs, x):
    y_kernel = gauss1.pdf(x[n_points // 4:-n_points // 4])
    y_func = func.pdf(x)
    true_conv = np.convolve(y_func, y_kernel, mode='full')[n_points // 4:  n_points * 5 // 4]
    true_conv /= np.mean(true_conv) * obs.rect_area()
    return true_conv


def test_conv_2D_simple():
    zfit.run.set_graph_mode(False)
    n_points = 200
    obs1 = zfit.Space("obs1", limits=(-5, 5))
    obs2 = zfit.Space("obs2", limits=(-6, 8))
    param1 = zfit.Parameter('param1', -3)
    param2 = zfit.Parameter('param2', 0.4)
    gauss1 = zfit.pdf.Gauss(0., param2, obs=obs1)
    gauss21 = zfit.pdf.Gauss(0.5, param2, obs=obs2)
    gauss22 = zfit.pdf.Gauss(0.3, param2 + 0.7, obs=obs2)
    func1 = zfit.pdf.Uniform(param1, param2, obs=obs1)
    func2 = zfit.pdf.Uniform(-1.2, -1, obs=obs1)
    func = zfit.pdf.SumPDF([func1, func2], 0.5)
    func = func * gauss21
    gauss = gauss1 * gauss22
    conv = zfit.pdf.FFTConvV1(func=func, kernel=gauss)

    start = (-5., -6.)
    stop = (5., 6.)
    x_tensor = tf.random.uniform((n_points, 2), start, stop)
    linspace = tf.linspace(start, stop, num=n_points)
    x_tensor = tf.reshape(x_tensor, (-1, 2))
    obs2d = obs1 * obs2
    x = zfit.Data.from_tensor(obs=obs2d, tensor=x_tensor)
    linspace_data = zfit.Data.from_tensor(obs=obs2d, tensor=linspace)
    probs_rnd = conv.pdf(x=x)
    probs = func.pdf(x=linspace_data)
    true_probs = true_conv_np(func, gauss, n_points=n_points, obs=obs2d, x=linspace)
    np.testing.assert_allclose(probs, true_probs, rtol=0.2, atol=0.1)
    integral = conv.integrate(limits=obs2d)
    assert pytest.approx(1, rel=1e-3) == integral.numpy()
    probs_np = probs_rnd.numpy()
    assert len(probs_np) == n_points
    # probs_plot = np.reshape(probs_np, (-1, n_points))
    # x_plot = linspace[0]
    # probs_plot_projx = np.sum(probs_plot, axis=0)
    # plt.plot(x_plot, probs_np)
    # probs_plot = np.reshape(probs_np, (n_points, n_points))
    # plt.imshow(probs_plot)
    # plt.show()

    # test the sampling
    conv_nosample = FFTConvV1NoSampling(func=func, kernel=gauss)

    npoints_sample = 10000
    sample = conv.sample(npoints_sample)
    sample_nosample = conv_nosample.sample(npoints_sample)
    x, y = z.unstack_x(sample)
    xns, yns = z.unstack_x(sample_nosample)

    import matplotlib.pyplot as plt
    plt.figure()
    plt.hist(x, bins=50, label='custom', alpha=0.5)
    plt.hist(xns, bins=50, label='fallback', alpha=0.5)
    plt.legend()
    plt.show()
