from astroquery.mast import Catalogs
from astropy import units as u
from prose import Observation
import re
import pandas as pd
import requests as req
import numpy as np
from prose.blocks import catalogs
from datetime import datetime


class TFOPObservation(Observation):
    """
    Subclass of Observation specific to TFOP observations
    """

    def __init__(self, photfile, name=None, time_verbose=False):
        """
        Parameters
        ----------
        photfile : str
            path of the `.phot` file to load
        name : str, optional
            To add if the TOI number is not given in target name (only number portion with planet: e.g. 1234.01), by default is None
        """
        super().__init__(photfile,time_verbose=time_verbose)
        if name is None:
            name = self.name
        self.tic_data = None
        self.toi_df = None
        tic = self.toi_to_tic(name)
        self._tic_id= f"{tic}"
        self._exofop_priors = self.find_exofop_priors(self._tic_id)
        self.ttf_priors = self.find_ttf_priors()
        self.toi = self.name.split('-')[1]
        try :
            self.planet = self.toi.split('.')[1]
        except IndexError:
            self.planet = '01'
        self.samples = None
        self.posteriors = None
        self.summary = None
        self.detrends = None

    # TESS specific methods
    # --------------------

    def toi_to_tic(self,name):
        try:
             nb = re.findall('\d*\.?\d+', name) #TODO add the possibility to do this with TIC ID rather than TOI number (also in obs)
             df = pd.read_csv("https://exofop.ipac.caltech.edu/tess/download_toi?toi=%s&output=csv" % nb[0])
             self.toi_df = df
             return df["TIC ID"][0]
        except KeyError:
            print('TIC not found')

    def find_exofop_priors(self,tic_id):
        try:
            df = pd.read_csv(f"https://exofop.ipac.caltech.edu/tess/download_stellar.php?id={tic_id}&csv", sep='|')
            return df.iloc[0]
        except KeyError:
            print('TIC not found')

    def find_ttf_priors(self):
        date = self.stack.night_date
        ttf_url = self.telescope.TTF_link.format(date=f'{date.strftime("%m-%d-%Y")}', tic_id=self.tic_id).replace(
            'print_html=1', 'print_html=2')
        r = req.get(ttf_url,
                    auth=('tess_nda_observer', 'F1nd_TE$S_PlaNets!'))
        ttf_priors = [{k:v for k,v in zip([l[:25]+l[-11:]
                                for l in [j.split(',')
                                for j in r.text[r.text.find('# ')+2:].splitlines()]][0], i)}
                            for i in [l[:25]+l[-11:]
                            for l in [j.split(',')
                            for j in r.text[r.text.find('# ')+2:].splitlines()]][1:]]
        for i, j in zip(ttf_priors, r.text.splitlines()[1:]):
            i['Comments'] = j[j.find('"') + 1:-j[::-1].find('"') - 1]

        ttf_priors[0]['Comments'] = ttf_priors[0]['Comments'].replace('σ', 'sigma')
        ttf_priors[0]['Comments'] = ttf_priors[0]['Comments'].replace('Δ', 'Delta')

        return ttf_priors[0]

    @property
    def tic_id(self):
        """TIC id from digits found in target name
        """
        return self._tic_id

    @tic_id.setter
    def tic_id(self, new):
        self._tic_id = f"{new}"

    @property
    def exofop_priors(self):
        """TIC id from digits found in target name
        """
        return self._exofop_priors

    @exofop_priors.setter
    def exofop_priors(self, tic):
        self._exofop_priors = self.find_exofop_priors(tic)

    @property
    def gaia_from_toi(self):
        """Gaia id from TOI id if TOI is in target name
        """
        if self.tic_id is not None:
            tic_id = ("TIC " + self.tic_id)
            catalog_data = Catalogs.query_object(tic_id, radius=.001, catalog="TIC")
            return f"{catalog_data['GAIA'][0]}"
        else:
            return None

    @property
    def tfop_prefix(self):
        date = self.stack.night_date.strftime("%Y%m%d")
        return f"TIC{self.tic_id}-{self.planet}_{date}_{self.telescope.name}_{self.filter}"

    # Catalog queries
    # ---------------
    def query_tic(self, cone_radius=None):
        """Query TIC catalog (through MAST) for stars in the field
        """
        self.stack = catalogs.TESSCatalog(mode="crossmatch")(self.stack)

    def set_tic_target(self, verbose=True):

        # using Gaia is easier to correct for proper motion... (discuss with LG)
        self.set_gaia_target(self.gaia_from_toi, verbose=verbose)

    def auto_modeling(self,detrends=None, use_dilution=0, limb_darkening_coefs=True, use_duration=False, tune=2000,draws=3000,cores=3,chains=2,target_accept=0.9,
                      **kwargs):

        """

        Parameters
        ----------
        detrends : dict
            detrending parameters, polynomial fit of systematics (airmass, sky, dx, dy, fwhm)
        use_duration : Bool
            True if the duration was used as prior instead of the stellar parameters to model the transit.
        dilution: tuple
            Magnitudes of the target star and contaminant star in the aperture (m1,m2).
        limb_darkening_coefs : bool or list
            if True, automatic calculation of the quadratic limb darkening coefficients using Claret 2012 if effective temperature
            of the star is < 5000K https://ui.adsabs.harvard.edu/abs/2012A%26A...546A..14C/abstract
            or Claret 2013 if effective temperature => 5000K https://ui.adsabs.harvard.edu/abs/2013A%26A...552A..16C/abstract
        tune : int
            Number of iterations to tune, defaults to 1000. Samplers adjust the step sizes, scalings or similar during
            tuning. Tuning samples will be drawn in addition to the number specified in the draws argument, and will be
            discarded unless discard_tuned_samples is set to False. (See PyMC3 documentation)
        draws : int
            The number of samples to draw. (See PyMC3 documentation)
        cores : int
            The number of chains to run in parallel. (See PyMC3 documentation)
        chains : int
            The number of chains to sample. (See PyMC3 documentation)
        target_accept : float
            float in [0, 1]. The step size is tuned such that we approximate this acceptance rate. Higher values like
            0.9 or 0.95 often work better for problematic posteriors. (See PyMC3 documentation)
        Returns
        -------
        A model obtained with the exoplanet package using the default NUTS sampler. The maximum a posteriori is stored in self.opt, the trace in
        self.samples and the values to be used in the transitmodel report page are stored in self.posteriors.
        """

        import pymc3 as pm
        import exoplanet as xo
        import pymc3_ext as pmx
        from prose.utils import earth2sun
        from prose import viz
        import arviz as az

        self.detrends = detrends

        X = self.polynomial(**detrends).T
        c = np.linalg.lstsq(X.T, self.diff_flux, rcond=None)[0]

        if isinstance(use_dilution,tuple):
            m1, m2 = use_dilution
            # For the contaminant star :
            F2 = 10 ** (m2 / (-2.5))
            # For the target star :
            F1 = 10 ** (m1 / (-2.5))
            _alpha = F2/F1
        else:
            _alpha=0

        if limb_darkening_coefs is True:
            logg = self.exofop_priors['log(g)']
            teff = self.exofop_priors['Teff (K)']
            ldcs = claret_2012(self.filter, teff, logg, 'L')

        if isinstance(limb_darkening_coefs, list):
            ldcs = limb_darkening_coefs

        with pm.Model() as model:
            # Systematics
            # -----------------
            w = pm.Flat('w', shape=len(X), testval=np.array(c))
            systematics = pm.Deterministic('systematics', w @ X)

            # Stellar parameters
            # -----------------
            u = xo.distributions.QuadLimbDark("u", testval=np.array(ldcs))
            star = xo.LimbDarkLightCurve(u[0], u[1])
            m_s = pm.Normal('m_s',self.exofop_priors["Mass (M_Sun)"],self.exofop_priors["Mass (M_Sun) Error"])
            r_s = pm.Normal('r_s', self.exofop_priors["Radius (R_Sun)"],self.exofop_priors["Radius (R_Sun) Error"])

            # Orbital parameters
            # -----------------
            t0 = pm.Normal('t0', 2450000 + float(self.ttf_priors['jd_mid']), 0.05)
            p = pm.Normal('P', float(self.ttf_priors['period(days)']), float(self.ttf_priors["period_unc(days)"]))
            b = pm.Uniform("b", 0, 1)
            depth = pm.Uniform("depth", 0, float(self.ttf_priors['depth(ppt)'])*10 *1e-3, testval=float(self.ttf_priors['depth(ppt)'])*1e-3)
            ror = pm.Deterministic("ror", star.get_ror_from_approx_transit_depth(depth, b))
            r_p = pm.Deterministic("r_p", ror * r_s)  # In solar radius
            r = pm.Deterministic('r', r_p * 1 / earth2sun)

            if use_duration:
                dur = float(self.ttf_priors['jd_end']) - float(self.ttf_priors['jd_start'])
                duration = pm.Normal('duration',dur,float(self.ttf_priors['duration_unc_hrs'])/24)
                # Keplerian orbit
                # ---------------
                orbit = xo.orbits.KeplerianOrbit(period=p, t0=t0, b=b,duration=duration)

            else:
                # Keplerian orbit
                # ---------------
                orbit = xo.orbits.KeplerianOrbit(period=p, t0=t0, r_star=r_s, b=b, m_star=m_s)

            alpha = pm.Normal('alpha', _alpha, 0.001)
            y_p = to_non_diluted(self.diff_flux, alpha)

            # starry light-curve
            # ---------------
            light_curves = star.get_light_curve(orbit=orbit, r=r_p, t=self.time)
            transit = pm.Deterministic("transit", pm.math.sum(light_curves, axis=-1))
            pm.Deterministic("dil_transit", to_diluted(transit, alpha, transit=True))
            pm.Deterministic("dil_systematics", to_diluted(systematics, alpha))

            # Let's track some parameters :
            pm.Deterministic("a", orbit.a)
            pm.Deterministic('i', orbit.incl * 180 / np.pi)
            pm.Deterministic('a/r_s', orbit.a / orbit.r_star)

            # Systematics and final model
            # ---------------------------
            # residuals = pm.Deterministic("residuals", obs.diff_flux - transit)
            mu = pm.Deterministic("mu", transit + systematics)

            # Likelihood function
            # -----------------------------
            pm.Normal("obs", mu=mu, sd=self.diff_error, observed=y_p)

            # Maximum a posteriori
            # --------------------
            self.opt = pmx.optimize(start=model.test_point)

        viz.plot_systematics_signal(self.time, to_non_diluted(self.diff_flux, self.opt['alpha']),
                                    self.opt['systematics'], self.opt['transit'])
        viz.paper_style()

        np.random.seed(42)

        with model:
            trace = pm.sample(
                tune=tune,
                draws=draws,
                start=self.opt,
                cores=cores,
                chains=chains,
                init="adapt_full",
                target_accept=target_accept,
                return_inferencedata=False,
                **kwargs
            )
        variables = ["P", "r", 't0', 'b', 'u', 'r_s', 'm_s', 'ror', 'depth', 'a', 'a/r_s', 'i','alpha']

        if use_duration:
            variables.append('duration')


        self.samples = pm.trace_to_dataframe(trace, varnames=variables)

        with model:
            self.summary = az.summary(
                trace, var_names=variables, round_to=4
            )

        self.posteriors = {}
        for i in self.summary.index:
            self.posteriors[i] = self.summary['mean'][i]
            self.posteriors[i + '_e'] = self.summary['sd'][i]


def claret_2012(filter, teff, logg, method):
    """

    Automatic calculation of the quadratic limb darkening coefficients using Claret 2012 if effective temperature
    of the star is < 5000K https://ui.adsabs.harvard.edu/abs/2012A%26A...546A..14C/abstract
    or Claret 2013 if effective temperature => 5000K https://ui.adsabs.harvard.edu/abs/2013A%26A...552A..16C/abstract
    Parameters
    ----------
    filter : str
        filter of the observation
    teff : int or float
        Effective temperature of the star in Kelvins
    logg : float
        Surface gravity in cm/s2
    method : str
        L or F Method (Least-Square or Flux Conservation)

    Returns
    -------
    The quadratic limb darkening coefficients a and b in a given filter for a given star.
    """
    if teff < 5000:
        df = pd.read_csv("https://cdsarc.cds.unistra.fr/ftp/J/A+A/546/A14/tableab.dat", sep='\s+')
        df.columns = ['logg', 'Teff', 'z', 'xi', 'u1', 'u2', 'Filter', 'Method', 'Model']
    else:
        df = pd.read_csv("https://cdsarc.cds.unistra.fr/ftp/J/A+A/552/A16/tableab.dat", sep='\s+')
        df.columns = ['logg', 'Teff', 'z', 'xi', 'u1', 'u2', 'Filter', 'Method', 'Model']

    filters = []
    if filter == 'I+z':
        filters.append('I')
        filters.append("z'")
    elif filter == 'z' or filter == 'r' or filter == 'g':
        filters.append(filter + "'")
    else:
        filters.append(filter)

    u1 = []
    u2 = []
    for k in filters:
        df2 = df.loc[(df.Filter == k) & (df.Method == method)]
        df2.reset_index(inplace=True, drop=True)
        idxs = np.argwhere(np.abs(df2.Teff.to_numpy() - teff) == np.abs(df2.Teff.to_numpy() - teff).min()).flatten()
        df3 = df2.iloc[idxs]
        idxs2 = np.argwhere(np.abs(df3.logg.to_numpy() - logg) == np.abs(df3.logg.to_numpy() - logg).min()).flatten()
        u1.append(df3.iloc[idxs2].u1.values[0])
        u2.append(df3.iloc[idxs2].u2.values[0])
    return np.mean(u1), np.mean(u2)


def to_diluted(non_dil_flux,alpha,transit=False):
    if transit is True:
        return ((non_dil_flux + 1 + alpha) / (1 + alpha)) -1
    else:
        return (non_dil_flux + alpha) / (1 + alpha)


def to_non_diluted(dil_flux,alpha):
    return (dil_flux * (1 + alpha)) - alpha