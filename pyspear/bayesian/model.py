import numpy as np
import pymc as pm
from prh import PRH

def make_model_powexp(zydata, use_sigprior="CSK", use_tauprior="CSK",
                              use_nuprior="Uniform", set_verbose=False):
    """
    powexp = model

    Parameters
    ----------
    zydata: zyLC object
        Generated by zyLC(zylist).
    use_sigprior: str or float, optional
        Prior for sigma: 'CSK', 'Vague', 'Gamma', 'None', or you could specify 
        a number so that the value of sigma will be fixed during the analysis 
        (default: 'CSK').
    use_tauprior: str or float, optional
        Prior for tau: 'CSK', 'Vague', 'IG', 'None', or you could specify 
        a number so that the value of tau will be fixed during the analysis
        (default: 'CSK').
    use_nuprior: str or float, optional
        Prior for nu: 'Uniform', or you could specify 
        a number so that the value of nu will be fixed during the analysis
        (default: 'Uniform').
    set_verbose: bool, optional
        Verbose mode (default: False)
    """
    #-------
    # light curve stat
    #-------
    cadence = zydata.cont_cad
    rx = zydata.rj
    ry = zydata.marr.max() - zydata.marr.min()
    #-------
    # priors
    #-------
    # sigma
    if use_sigprior == "CSK":
        @pm.stochastic
        def sigma(value=ry/4.):
            def logp(value):
                if (value > 0.0):
                   return(-np.log(value))
                elif(value < 0.0):
                    return(-np.Inf)
    elif use_sigprior == "Vague":
        invsigsq = pm.Gamma('invsigsq' , alpha=0.001, beta=0.001, value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            return(1./np.sqrt(invsigsq))
    elif use_sigprior == "Gamma":
        invsigsq = pm.Gamma('invsigsq' , alpha=2.0, beta=1./(ry/4.0)**2., value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            return(1./np.sqrt(invsigsq))
    elif use_sigprior == "None":
#        sigma = pm.Uninformative("sigma", value=ry/4.)
        invsigsq = pm.Uninformative('invsigsq', value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            if np.abs(invsigsq) < 1.e-6:
                return(1.e6)
            else:
                return(1./np.sqrt(np.abs(invsigsq)))
    else:
        try:
            sigma = float(use_sigprior)
            if set_verbose:
                print("sigma is fixed to be %.3f"%sigma)
        except:
            raise RuntimeError("no such prior for sigma %s"%use_sigprior)

    # tau
    if use_tauprior == "CSK":
        # double-lobed log prior on tau, stemmed from CSK's original code
        @pm.stochastic
        def tau(value=np.sqrt(rx*cadence)):
            def logp(value):
                if (10000 > value > 1.0*cadence):
                    return(-np.log(value/(1.0*cadence)))
                elif(0.0 < value <= 1.0*cadence):
                    return(-np.log(1.0*cadence/value))
                else:
                    return(-np.Inf)
    elif use_tauprior == "Vague":
        # inverse gamma prior on tau, penalty on extremely small or large scales.
        tau   = pm.Gamma('tau' , alpha=0.001, beta=0.001, value=np.sqrt(rx*cadence))
    elif use_tauprior == "IG":
        # inverse gamma prior on tau, penalty on extremely small or large scales.
        tau   = pm.InverseGamma('tau' , alpha=2., beta=np.sqrt(rx*cadence), value=np.sqrt(rx*cadence))
    elif use_tauprior == "None":
        tau   = pm.Uninformative("tau", value=np.sqrt(rx*cadence))
    else:
        try:
            tau   = float(use_tauprior)
            if set_verbose:
                print("tau is fixed to be %.3f"%tau)
        except:
            raise RuntimeError("no such prior for tau %s"%use_tauprior)

    # nu
    if use_nuprior == "Uniform":
        # uniform prior on nu
        nu    = pm.Uniform('nu', 0, 2, value=1.0)
    else:
        try:
            nu   = float(use_nuprior)
            if set_verbose:
                print("nu is fixed to be %.3f"%nu)
        except:
            raise RuntimeError("no such prior for nu %s"%use_nuprior)

    #-------
    # model
    #-------
    guess = [np.sqrt(rx*cadence), ry/4.0, 1.0]
    @pm.stochastic(observed=True)
    def model_powexp(value=guess,
                     sigma=sigma, tau=tau, nu=nu):
        par=[sigma, tau, nu]
        prh = PRH(zydata, covfunc="pow_exp", 
                               sigma=par[0], tau=par[1], nu=par[2])
        out = prh.loglike_prh()
        return(out[0])

    return(locals())


def make_model_cov3par(zydata, covfunc="pow_exp",
                              use_sigprior="CSK", 
                              use_tauprior="CSK", 
                              use_nuprior="Uniform",
                              par_init=None,
                              set_verbose=False):
    """
    Make 1D Gaussian models with covariance functions that have three parameters.

    Parameters
    ----------
    zydata: zyLC object
        Generated by zyLC(zylist).
    covfunc: str, optional
        Name of the covariance function, currently available: "pow_exp", 
        "matern", and "pareto_exp".
    use_sigprior: str or float, optional
        Prior for sigma: 'CSK', 'Vague', 'Gamma', 'None', or you could specify 
        a number so that the value of sigma will be fixed during the analysis (default: 'CSK').
    use_tauprior: str or float, optional
        Prior for tau: 'CSK', 'Vague', 'IG', 'None', or you could specify 
        a number so that the value of tau will be fixed during the analysis (default: 'CSK').
    use_nuprior: str or float, optional
        Prior for nu: 'Uniform', or you could specify 
        a number so that the value of nu will be fixed during the analysis (default: 'Uniform').
    set_verbose: bool, optional
        Verbose mode (default: False)
    """
    #-------
    # light curve stat
    #-------
    cadence = zydata.cont_cad
    rx = zydata.rj
    ry = zydata.marr.max() - zydata.marr.min()
    #-------
    # covfunc-dependent initial values
    #-------
    #  [tau, sigma, nu] 
    if par_init is None:
        sigma_init  = ry/4.0
        tau_init    = np.sqrt(rx*cadence)
        if covfunc is "pow_exp":
            nu_init     = 1.0
        elif covfunc is "matern":
            nu_init     = 0.5
        elif covfunc is "pareto_exp":
            nu_init     = 1.5
        elif covfunc is "kepler_exp":
            nu_init     = 0.1
        par_init = [sigma_init, tau_init, nu_init]
    # truncation limit for the third parameter
    if covfunc is "pow_exp":
        nu_min = 0.0
        nu_max = 1.999
    elif covfunc is "matern":
        nu_min = 0.001
        nu_max = 2.000
    elif covfunc is "pareto_exp":
        nu_min = 0.001
        nu_max = 2.000
    elif covfunc is "kepler_exp":
        nu_min = 0.001
        nu_max = 0.800
    #-------
    # priors
    #-------
    # sigma
    if use_sigprior == "CSK":
        @pm.stochastic
        def sigma(value=ry/4.):
            def logp(value):
                if (value > 0.0):
                   return(-np.log(value))
                elif(value < 0.0):
                    return(-np.Inf)
    elif use_sigprior == "Vague":
        invsigsq = pm.Gamma('invsigsq' , alpha=0.001, beta=0.001, value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            return(1./np.sqrt(invsigsq))
    elif use_sigprior == "Gamma":
        invsigsq = pm.Gamma('invsigsq' , alpha=2.0, beta=1./(ry/4.0)**2., value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            return(1./np.sqrt(invsigsq))
    elif use_sigprior == "None":
        invsigsq = pm.Uninformative('invsigsq', value=1./(ry/4.0)**2.)
        @pm.deterministic
        def sigma(name="sigma", invsigsq=invsigsq):
            if np.abs(invsigsq) < 1.e-6:
                return(1.e6)
            else:
                return(1./np.sqrt(np.abs(invsigsq)))
    else:
        try:
            sigma = float(use_sigprior)
            if set_verbose:
                print("sigma is fixed to be %.3f"%sigma)
        except:
            raise RuntimeError("no such prior for sigma %s"%use_sigprior)

    # tau
    if use_tauprior == "CSK":
        # double-lobed log prior on tau, from CSK's original code
        @pm.stochastic
        def tau(value=np.sqrt(rx*cadence)):
            def logp(value):
                if (10000 > value > 1.0*cadence):
                    return(-np.log(value/(1.0*cadence)))
                elif(0.0 < value <= 1.0*cadence):
                    return(-np.log(1.0*cadence/value))
                else:
                    return(-np.Inf)
    elif use_tauprior == "Vague":
        # inverse gamma prior on tau, penalty on extremely small or large scales.
        tau   = pm.Gamma('tau' , alpha=0.001, beta=0.001, value=np.sqrt(rx*cadence))
    elif use_tauprior == "IG":
        # inverse gamma prior on tau, penalty on extremely small or large scales.
        tau   = pm.InverseGamma('tau' , alpha=2., beta=np.sqrt(rx*cadence), value=np.sqrt(rx*cadence))
    elif use_tauprior == "None":
        tau   = pm.Uninformative("tau", value=np.sqrt(rx*cadence))
    else:
        try:
            tau   = float(use_tauprior)
            if set_verbose:
                print("tau is fixed to be %.3f"%tau)
        except:
            raise RuntimeError("no such prior for tau %s"%use_tauprior)

    # nu
    if use_nuprior == "Uniform":
        # uniform prior on matern nu
        nu    = pm.Uniform('nu', nu_min, nu_max, value=nu_init)
    else:
        try:
            nu   = float(use_nuprior)
            if set_verbose:
                print("nu is fixed to be %.3f"%nu)
        except:
            raise RuntimeError("no such prior for nu %s"%use_nuprior)

    #-------
    # model
    #-------
    guess = par_init
    @pm.stochastic(observed=True)
    def model_cov3par(value=guess, sigma=sigma, tau=tau, nu=nu):
        par=[sigma, tau, nu]
        prh = PRH(zydata, covfunc=covfunc, sigma=par[0], tau=par[1], nu=par[2])
        out = prh.loglike_prh()
        return(out[0])

    return(locals())
