#!/usr/local/bin/env python
from __future__ import division
import numpy as np
import pandas as pd
from lmfit import Parameters, Minimizer
from radd.utils import *
from radd import RADD

def fit_reactive_model(y, inits={}, depends=['xx'], model='radd', ntrials=5000, maxfun=5000, ftol=1.e-3, xtol=1.e-3, all_params=0, disp=False):

    if 'pGo' in inits.keys(): del inits['pGo']
    if 'ssd' in inits.keys(): del inits['ssd']

    p=Parameters()
    for key, val in inits.items():
        if key in depends:
            p.add(key, value=val, vary=1)
            continue
        p.add(key, value=val, vary=all_params)

    popt = Minimizer(ssre_minfunc, p, fcn_args=(y, ntrials),
        fcn_kws={'model':model}, method='Nelder-Mead')
    popt.fmin(maxfun=maxfun, ftol=ftol, xtol=xtol, full_output=True, disp=disp)

    params={k: p[k].value for k in p.keys()}
    params['chi']=popt.chisqr
    resid=popt.residual; yhat=y+resid

    return params, yhat


def ssre_minfunc(p, y, ntrials, model='radd', tb=.650, dflist=[], intervar=False):

	try:
		theta={k:p[k].value for k in p.keys()}
	except Exception:
		theta=p.copy()
	theta['pGo']=.5; delays=np.arange(0.200, 0.450, .05)

	for ssd in delays:
		theta['ssd']=ssd
		simdf = simulate(theta, ntrials, tb=tb, model=model, intervar=intervar)
		dflist.append(simdf)

	yhat = rangl_re(pd.concat(dflist))

	return yhat - y


def simulate(theta, ntrials=2000, tb=.650, model='radd', intervar=False, return_traces=False):

	if intervar:
		theta=get_intervar_ranges(theta)

	dvg, dvs = RADD.run(theta, ntrials=ntrials, model=model, tb=tb)

	if return_traces:
		return dvg, dvs

	return gen_resim_df(dvg, dvs, theta, tb=tb, model=model)


def gen_resim_df(DVg, DVs, theta, model='radd', tb=.650, dt=.0005):

	nss=len(DVs)
	ngo=len(DVg) - nss

	theta=update_params(theta)
	tr=theta['tt'];	a=theta['a']; ssd=theta['ssd']
	#define RT functions for upper and lower bound processes
	upper_rt = lambda x, DV: np.array([tr + np.argmax(DVi>=x)*dt if np.any(DVi>=x) else 999 for DVi in DV])
	lower_rt = lambda DV: np.array([ssd + np.argmax(DVi<=0)*dt if np.any(DVi<=0) else 999 for DVi in DV])

	#check for and record go trial RTs
	grt = upper_rt(a, DVg[nss:, :])
	if model=='abias':
		ab=a+theta['ab']
		delay = np.ceil((tb-tr)/dt) - np.ceil((tb-ssd)/dt)
		#check for and record SS-Respond RTs that occur before boundary shift
		ert_pre = upper_rt(a, DVg[:nss, :delay])
		#check for and record SS-Respond RTs that occur POST boundary shift (t=ssd)
		ert_post = upper_rt(ab, DVg[:nss, delay:])
		#SS-Respond RT equals the smallest value
		ert = np.fmin(ert_pre, ert_post)
	else:
		#check for and record SS-Respond RTs
		ert = upper_rt(a, DVg[:nss, :])

        if model in ['radd', 'ipb','abias']:
                ssrt = lower_rt(DVs)
        else:
                ssrt = upper_rt(a, DVs)

	# Prepare and return simulations df
    # Compare trialwise SS-Respond RT and SSRT to determine outcome (i.e. race winner)
	stop = np.array([1 if ert[i]>si else 0 for i, si in enumerate(ssrt)])
	response = np.append(np.abs(1-stop), np.where(grt<tb, 1, 0))
	# Add "choice" column to pad for error in later stages
	choice=np.where(response==1, 'go', 'stop')
	# Condition
	ssdlist = [int(ssd*1000)]*nss+[1000]*ngo
	ttypes=['stop']*nss+['go']*ngo
	# Take the shorter of the ert and ssrt list, concatenate with grt
	rt=np.append(np.fmin(ert,ssrt), grt)

	simdf = pd.DataFrame({'response':response, 'choice':choice, 'rt':rt, 'ssd':ssdlist, 'trial_type':ttypes})
	# calculate accuracy for both trial_types
	simdf['acc'] = np.where(simdf['trial_type']==simdf['choice'], 1, 0)
	simdf.rt.replace(999, np.nan, inplace=True)

	return simdf


def simple_resim(theta, ssdlist=range(200, 450, 50), ntrials=2000):
	ssdlist = np.array(ssdlist)*.001
	dflist = []
	theta['pGo']=.5
	for ssd in ssdlist:
		theta['ssd'] = ssd
		dvg, dvs = RADD.run(theta, tb=.650, ntrials=ntrials)
		df = analyze_reactive_trials(dvg, dvs, theta)
		dflist.append(df)

	return pd.concat(dflist)
