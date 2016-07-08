#!/usr/local/bin/env python
from __future__ import division
import sys
from copy import deepcopy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from radd.tools import colors, messages, analyze
from IPython.display import HTML, Javascript, display
import warnings

warnings.simplefilter('ignore', np.RankWarning)
sns.set(style='white', context='notebook', rc={'text.color': 'black', 'axes.labelcolor': 'black', 'figure.facecolor': 'white'}, font_scale=1.5)

cdict = colors.get_cpals('all')
rpal = cdict['rpal']
bpal = cdict['bpal']
gpal = cdict['gpal']
ppal = cdict['ppal']
heat = cdict['heat']
cool = cdict['cool']
slate = cdict['slate']

def unpack_vector(vector, nlevels=1, nquant=5, nssd=1, kde_quant=False):
    unpacked = []
    vector = vector.reshape(nlevels, int(vector.size/nlevels))
    for v in vector:
        if nssd>1:
            # get accuracy at each SSD
            presp = v[1:1+nssd]
        else:
            # get go, stop accuracy
            presp = v[:2]
        quant = v[-nquant*2:]
        quant_cor = quant[:nquant]
        quant_err = quant[-nquant:]
        if kde_quant:
            quant_cor = analyze.kde_fit_quantiles([quant_cor], bw=.01)
            quant_err = analyze.kde_fit_quantiles([quant_err], bw=.01)
        unpacked.append([presp, quant_cor, quant_err])
    return unpacked

def plot_model_fits(y, yhat, fitparams, kde_quant=True, palette=bpal, save=False, cdf=True):
    """ main plotting function for displaying model fit predictions over data
    """
    nlevels = y.ndim
    fitparams['nlevels'] = nlevels
    quantiles = fitparams['quantiles']
    ssd, nssd, nss, nss_per, ssd_ix = fitparams['ssd_info']
    f, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    axes = np.asarray(axes)
    clrs_lvl = palette(nlevels)
    y_data = unpack_vector(y, nlevels=nlevels, nquant=quantiles.size, nssd=nssd, kde_quant=False)
    yhat_data = unpack_vector(yhat, nlevels=nlevels, nquant=quantiles.size, nssd=nssd, kde_quant=False)
    y_kde = unpack_vector(y, nlevels=nlevels, nquant=quantiles.size, nssd=nssd, kde_quant=True)
    yhat_kde = unpack_vector(yhat, nlevels=nlevels, nquant=quantiles.size, nssd=nssd, kde_quant=True)
    if nssd>1:
        ssds = ssd.mean(axis=0).squeeze()*1e3
        scx = np.array([np.float(d) for d in ssds])
        plot_acc = scurves
    else:
        scx = np.array([0, 1])
        plot_acc = plot_accuracy
    labels = get_plot_labels(fitparams)
    for i in range(nlevels):
        ax1, ax2, ax3 = axes
        c = clrs_lvl[i]
        lemp, lhat = labels[i]
        plot_acc([y_data[i][0], yhat_data[i][0]], x=scx, colors=[c,c], labels=labels[i], ax=ax1)
        plot_quantiles(y_data[i], yhat_data[i], color=c, axes=[ax2, ax3], kde=False, labels=labels[i])
        plot_quantiles(y_kde[i], yhat_kde[i], color=c, axes=[ax2, ax3], kde=True)

    ax1.set_title('Stop Accuracy', position=(.5, 1.02))
    ax2.set_title('Correct RT Quantiles', position=(.5, 1.02))
    ax3.set_title('Error RT Quantiles', position=(.5, 1.02))
    for ax in [ax2, ax3]:
        qdata = np.hstack([arr[1:] for arr in yhat_data]).flatten()
        xxlim = (qdata.min()-.05, qdata.max()+.05)
        xxticks = [xxlim[0], np.mean(xxlim), xxlim[-1]]
        xxtls = ["{:.2f}".format(xtl) for xtl in xxticks]
        plt.setp(ax, xlim=xxlim, xticks=xxticks, xticklabels=xxtls, xlabel='RT (s)')
    ax1.set_xlabel('SSD (ms)')
    plt.tight_layout()
    if save:
        savestr = '_'.join([fitparams['kind'], str(fitparams['idx'])+'.png'])
        plt.savefig(savestr, dpi=600)
        plt.close('all')

def scurves(lines=[],  ax=None, colors=None, labels=None, x=None, get_pse=False, pretune_fx='interpolate'):
    """ plotting function for displaying model-predicted
    stop curve (across SSDs) over empirical estimates
    """
    if ax is None:
        f, ax = plt.subplots(1, figsize=(5.5, 6))
    if colors is None:
        colors = slate(len(lines))
    if labels is None:
        labels = [''] * len(lines)
    if x is None:
        x = np.arange(len(lines[0]), dtype='float')*50
    fc = (0.,0.,0.,.01)
    pse=[]
    for i, yi in enumerate(lines):
        if pretune_fx=='interpolate':
            xsim, ysim = analyze.scurve_interpolate(x, yi)
        elif pretune_fx=='polynomial':
            xsim, ysim = analyze.scurve_poly_fit(x, yi)
        xsim, ysim = analyze.fit_sigmoid(xsim, ysim)
        idx = (np.abs(ysim - .5)).argmin()
        pse.append(xsim[idx])
        # Plot the results
        if i%2:
            ax.plot(x, yi, lw=0., color=colors[i],  marker='o', ms=5)
            ax.plot(xsim, ysim, lw=2, color=colors[i], label=labels[i])
            continue
        ax.plot(x, yi, lw=0., color=colors[i], marker='o', ms=9, mfc=fc, mec=colors[i], mew=1.5)
        ax.plot(xsim, ysim, linestyle='--', lw=2, color=colors[i], label=labels[i])
    xxlim = (xsim[0], xsim[-1])
    plt.setp(ax, xticks=x, xlim=xxlim, ylim=(-.01, 1.05), yticks=np.arange(0, 1.2, .2), ylabel='P(Stop)')
    ax.legend(loc=0)
    ax.set_xlim(xxlim[0], xxlim[1])
    plt.tight_layout()
    sns.despine()
    if get_pse:
        return pse

def plot_quantiles(y_data, yhat_data, axes=None, color=None, labels=None, kde=False, quantiles=np.array([.1, .3, .5, .7, .9]), bw=.01):
    """ plotting function for displaying model-predicted
    quantile-probabilities over empirical estimates
    """
    fc = (0.,0.,0.,.01)
    c = color
    if axes is not None:
        ax2, ax3 = axes
    else:
        f, (ax2, ax3) = plt.subplots(1, 2, figsize=(10, 4))
    qc, qc_hat = [y_data[1], yhat_data[1]]
    qe, qe_hat = [y_data[2], yhat_data[2]]
    if kde:
        sns.kdeplot(qc, cumulative=1, color=c, ax=ax2, linewidth=2, linestyle='-', bw=bw)
        sns.kdeplot(qe, cumulative=1, color=c, ax=ax3, linewidth=2, linestyle='-', bw=bw)
        sns.kdeplot(qc_hat, cumulative=1, color=c, ax=ax2, linewidth=2, linestyle='--', bw=bw)
        sns.kdeplot(qe_hat, cumulative=1, color=c, ax=ax3, linewidth=2, linestyle='--', bw=bw)
    else:
        ax2.plot(qc, quantiles, color=c, linewidth=0, marker='o', ms=5, label=labels)
        ax3.plot(qe, quantiles, color=c, linewidth=0, marker='o', ms=5, label=labels)
        ax2.plot(qc_hat, quantiles, mec=c, linewidth=0, marker='o', ms=8, mfc=fc, mew=1.5, label=labels)
        ax3.plot(qe_hat, quantiles, mec=c, linewidth=0, marker='o', ms=8, mfc=fc, mew=1.5, label=labels)

def plot_accuracy(lines=[], yerr=None, x=np.array([0, 1]), ax=None, linestyles=None, colors=None, labels=None, **kwargs):
    """ plotting function for displaying model-predicted
    stop probability (at mean SSD) on top of empirical estimates
    (used when data is collected using tracking procedure to est. SSRT)
    """
    if ax is None:
        f, ax = plt.subplots(1, figsize=(5.5, 6))
    if colors is None:
        colors = slate(len(lines))
    if labels is None:
        labels = [''] * len(lines)
    if linestyles is None:
        linestyles = ['-'] * len(lines)
    lines = [(line) if type(line) == list else line for line in lines]
    if x is None:
        x = np.arange(len(lines[0]), dtype='float')
    for i, yi in enumerate(lines):
        xjitter = x + (i*.02)
        color = colors[i]
        if yerr is not None:
            ax.errorbar(xjitter, yi, yerr=yerr[i], color=color, lw=2, elinewidth=2, ecolor=color)
        else:
            ax.plot(xjitter, yi, linestyle=linestyles[i], lw=2, color=color, label=labels[i])

    plt.setp(ax, xticks=x, xlim=(-0.25, 1.25), ylim=(.25, 1.05), yticks=(.3, 1))
    ax.set_ylabel('Percent Correct'); ax.legend(loc=0)

    ax.set_xticklabels(['Go', 'Stop'])
    plt.tight_layout()
    sns.despine()

def get_plot_labels(fitparams):
    lbls = np.hstack(fitparams['clmap'].values())
    labels = [[lbl + dtype for dtype in ['_data', '_model']] for lbl in lbls]
    return labels

def plot_kde_cdf(quant, bw=.1, ax=None, color=None):
    if ax is None:
        f, ax = plt.subplots(1, figsize=(5, 5))
    if color is None:
        color = 'k'
    kdefits = analyze.kde_fit_quantiles(quant, bw=bw)
    sns.kdeplot(kdefits, cumulative=True,  color=color, ax=ax, linewidth=2.5)
    ax.set_xlim(kdefits.min() * .94, kdefits.max() * 1.05)
    ax.set_ylabel('P(RT<t)')
    ax.set_xlabel('RT (s)')
    ax.set_ylim(-.05, 1.05)
    ax.set_xticklabels(ax.get_xticks() * .1)
    plt.tight_layout()
    sns.despine()