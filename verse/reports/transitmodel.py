import numpy as np
import matplotlib.pyplot as plt
from prose import Observation
from prose.fluxes import pont2006
from prose.utils import binning
from os import path
from prose import viz
from prose.reports.core import LatexTemplate
import pandas as pd
import collections
import corner
from .latex_template import VerseLatexTemplate
from ..tfop_observation import to_non_diluted, to_diluted

template_folder = path.abspath(path.join(path.dirname(__file__), "..", "..", "latex"))

class TransitModel(VerseLatexTemplate):

    def __init__(self, obs, transit, trend=None, expected=None, posteriors={}, use_duration=False, use_dilution=False, rms_bin=5/24/60,
                 template_name="transitmodel.tex"):
        """Transit modeling report

        Parameters
        ----------
        obs : Observation
            observation to model
        transit : 1D array
            transit model
        trend : 1D array, optional
            trend model, by default None
        expected : tuple, optional
            tuple of (t0, duration) of expected transit, by default None
        posteriors : dict
            Results of the posterior distributions of the fit including mean and standard deviation.
        use_duration : Bool
            True if the duration was used as prior instead of the stellar parameters to model the transit.
        use_dilution: Bool
            True if the aperture of the target star includes a contaminating star.
        rms_bin : float, optional
            [description], by default 0.005
        style : str, optional
            [description], by default "paper"
        template_name : str, optional
            [description], by default "transitmodel.tex"
        """
        super().__init__(template_name)
        self.obs = obs
        # Some paths
        # ----------
        self.destination = None
        self.report_name = None
        self.use_duration = use_duration
        self.use_dilution = use_dilution
        self.figure_destination = None
        self.transit_model = transit
        self.trend_model = trend if trend is not None else np.zeros_like(self.obs.time)
        self.residuals = self.obs.diff_flux - to_diluted(self.trend_model, self.obs.opt['alpha']) - to_diluted(
            self.transit_model, self.obs.opt['alpha'], transit=True)
        intransit = self.transit_model < -1e-6
        self.ingress = self.obs.time[intransit][0]
        self.egress = self.obs.time[intransit][-1]
        self.t14 = (self.egress - self.ingress) * 24 * 60
        self.snr = self.snr()
        self.rms_bin = rms_bin
        self.rms = self.rms_binned()
        self.priors = self.get_priors()
        self.posteriors = posteriors #TODO if posteriors is empty, avoid the KeyError in the obstable, replace by nan or None or whatever
        self.expected = expected
        self.obstable = [
            ["Parameters", "Model", "TESS"],
            ["u1", f"{self.posteriors['u[0]']}" "$\pm$" f"{self.posteriors['u[0]_e']}", "-"],
            ["u2", f"{self.posteriors['u[1]']}" "$\pm$" f"{self.posteriors['u[1]_e']}", "-"],
            ["R*", f"{self.posteriors['r_s']}" "$\pm$" f"{self.posteriors['r_s_e']}""R$_{\odot}$", f"{self.priors['rad_s']:.4f}" "$\pm$" f"{self.priors['rad_s_e']:.4f}" "R$_{\odot}$"],
            ["M*", f"{self.posteriors['m_s']}" "$\pm$" f"{self.posteriors['m_s_e']}""M$_{\odot}$", f"{self.priors['mass_s']:.4f}" "$\pm$" f"{self.priors['mass_s_e']:.4f}" "M$_{\odot}$"],
            ["P",f"{self.posteriors['P']}" "$\pm$" f"{self.posteriors['P_e']}""d", f"{self.priors['period']:.2e}" "$\pm$" f"{self.priors['period_e']:.2e}""d"],
            ["Rp", f"{self.posteriors['r']}" "$\pm$" f"{self.posteriors['r_e']}""R$_{\oplus}$", f"{self.priors['rad_p']:.4f}" "$\pm$" f"{self.priors['rad_p_e']:.4f}" "R$_{\oplus}$"],
            ["Tc", f"{self.posteriors['t0']}" "$\pm$" f"{self.posteriors['t0_e']}" , f"{2450000+float(self.obs.ttf_priors['jd_mid'])}" "$\pm$" f"{float(self.obs.ttf_priors['T_0_unc']):.2e}"],
            ["b", f"{self.posteriors['b']}" "$\pm$" f"{self.posteriors['b_e']}", "-"],
            ["Duration", f"{self.t14:.2f} min", f"{self.priors['duration']:.2f}" "$\pm$" f"{self.priors['duration_e']:.2f} min"],
            ["(Rp/R*)\u00b2", f"{self.posteriors['depth'] * 1e3:.2f}" 'e-3' "$\pm$" f"{self.posteriors['depth_e'] * 1e3:.2f}" 'e-3',"-"],
            ["Apparent depth (min. flux)", f"{np.abs(min(self.transit_model)) * 1e3:.2f}" 'e-3',  f"{self.priors['depth']:.2f}" 'e-3' "$\pm$" f"{self.priors['depth_e']:.2f}" 'e-3'],
            ["a/R*", f"{self.posteriors['a/r_s']}" "$\pm$" f"{self.posteriors['a/r_s_e']}", "-"],
            ["i", f"{self.posteriors['i']}" "$\pm$" f"{self.posteriors['i_e']}", "-"],
            ["SNR", f"{self.snr:.2f}", "-"],
            ["RMS per bin (%s min)" % f"{self.rms[1]:.1f}", f"{self.rms[0]:.2e}", "-"],
        ]
        if self.use_dilution:
            self.obstable.append(["Dilution factor", f"{self.posteriors['alpha']:.2f}","-"])
            self.obstable.append(["Apparent depth (min. flux) (diluted)", f"{np.abs(min(self.obs.opt['dil_transit'])) * 1e3:.2f}" 'e-3',"-"])

    def plot_ingress_egress(self):
        plt.axvline(self.expected[0] + self.expected[1] / 2, c='C4', alpha=0.4, label='predicted ingress/egress')
        plt.axvline(self.expected[0] - self.expected[1] / 2, c='C4', alpha=0.4)
        plt.axvline(self.ingress, ls='--', c='C4', alpha=0.4, label='observed ingress/egress')
        plt.axvline(self.egress, ls='--', c='C4', alpha=0.4)
        _, ylim = plt.ylim()

    def make_figures(self, destination):
        self.plot_lc_model()
        plt.savefig(path.join(destination, "model.png"), dpi=self.dpi)
        plt.close()
        self.make_corner_plot()
        plt.savefig(path.join(destination, "Corner_plot.png"), dpi=self.dpi)
        plt.close()
        #TEST


    def make(self, destination):
        self.make_report_folder(destination)
        self.make_figures(self.figure_destination)
        open(self.tex_destination, "w").write(self.template.render(
            obstable=self.obstable
        ))
        self.to_csv_report(destination)

    def plot_lc_model(self):

        viz.plot_systematics_signal(self.obs.time, to_non_diluted(self.obs.diff_flux, self.obs.opt['alpha']),
                                        self.trend_model, self.transit_model)

        # plot expected and observed transits
        std = 2 * np.std(to_non_diluted(self.obs.diff_flux, self.obs.opt['alpha']))
        t0, duration = self.expected
        viz.plot_section(1 + std, "expected", t0, duration, c="k")
        duration = self.egress - self.ingress
        viz.plot_section(1 + std + 0.005, "observed", self.ingress + duration / 2, duration, c="C0")

        self.obs.plot_meridian_flip()
        plt.tight_layout()
        self.style()

    def make_corner_plot(self):
        if self.obs.samples is not None:
            truths = [self.obs.opt['P'], self.obs.opt['r'], self.obs.opt['t0'], self.obs.opt['b'], self.obs.opt['u'][0],
                      self.obs.opt['u'][1], self.obs.opt['r_s'], self.obs.opt['m_s'], self.obs.opt['ror'],self.obs.opt['depth'],
                      self.obs.opt['a'], self.obs.opt['a/r_s'], self.obs.opt['i'],self.obs.opt['alpha']]
            if self.use_duration:
                truths.append(self.obs.opt['duration'])

            fig = corner.corner(self.obs.samples,
                                truths=truths)
            fig.patch.set_facecolor('xkcd:white')

    def to_csv_report(self, destination):
        """
        This one adds de-trended light-curve
        """
        destination = path.join(destination,'measurements.txt')
        comparison_stars = self.obs.comps[self.obs.aperture]
        list_diff = ["DIFF_FLUX_C%s" % i for i in comparison_stars]
        list_err = ["DIFF_ERROR_C%s" % i for i in comparison_stars]
        list_columns = [None] * (len(list_diff) + len(list_err))
        list_columns[::2] = list_diff
        list_columns[1::2] = list_err
        list_diff_array = [self.obs.diff_fluxes[self.obs.aperture, i] for i in comparison_stars]
        list_err_array = [self.obs.diff_errors[self.obs.aperture, i] for i in comparison_stars]
        list_columns_array = [None] * (len(list_diff_array) + len(list_err_array))
        list_columns_array[::2] = list_diff_array
        list_columns_array[1::2] = list_err_array

        df = pd.DataFrame(collections.OrderedDict(
            {
                "BJD-TDB" if self.obs.time_format == "bjd_tdb" else "JD-UTC": self.obs.time,
                "DIFF_FLUX_T%s" % self.obs.target: self.obs.diff_flux,
                "DIFF_FLUX_T%s_DETRENDED" % self.obs.target: self.obs.diff_flux - to_diluted(self.obs.opt['systematics'],self.obs.opt['alpha'])+1,
                "DIFF_ERROR_T%s" % self.obs.target: self.obs.diff_error,
                **dict(zip(list_columns, list_columns_array)),
                "dx": self.obs.dx,
                "dy": self.obs.dy,
                "FWHM": self.obs.fwhm,
                "SKYLEVEL": self.obs.sky,
                "AIRMASS": self.obs.airmass,
                "EXPOSURE": self.obs.exptime,
            })
        )
        return df.to_csv(destination, sep="\t", index=False)

    def snr(self):
        wn, rn = pont2006(self.obs.time, self.residuals, plot=False)
        texp = np.mean(self.obs.exptime)
        _duration = (self.egress - self.ingress) * 24 * 60 * 60
        n = int(_duration / texp)
        depth = np.abs(min(to_diluted(self.transit_model, self.obs.opt['alpha'], transit=True)))
        return depth / (np.sqrt(((wn ** 2) / n) + (rn ** 2)))

    def rms_binned(self):
        bins, flux, std = binning(self.obs.time, self.residuals, bins=self.rms_bin, std=True)
        return np.std(flux), self.rms_bin * 24 * 60

    def get_priors(self):
        priors = {}
        if self.obs.exofop_priors is not None:
            priors['rad_p'] = self.obs.toi_df['Planet Radius (R_Earth)'][0]
            priors['rad_p_e'] = self.obs.toi_df['Planet Radius (R_Earth) err'][0]
            priors['rad_s'] = self.obs.exofop_priors['Radius (R_Sun)']
            priors['rad_s_e'] = self.obs.exofop_priors['Radius (R_Sun) Error']
            priors['mass_s'] = self.obs.exofop_priors['Mass (M_Sun)']
            priors['mass_s_e'] = self.obs.exofop_priors['Mass (M_Sun) Error']
            priors['period'] = float(self.obs.ttf_priors['period(days)'])
            priors['period_e'] = float(self.obs.ttf_priors["period_unc(days)"])
            priors['duration'] = (float(self.obs.ttf_priors['jd_end']) - float(self.obs.ttf_priors['jd_start'])) * 24 * 60
            priors['duration_e'] = float(self.obs.ttf_priors['duration_unc_hrs'])/24
            priors['depth'] = self.obs.toi_df['Depth (ppm)'][0] / 1e3
            priors['depth_e'] = self.obs.toi_df['Depth (ppm) err'][0] / 1e3
        else:
            priors['rad_p'] = np.nan
            priors['rad_p_e'] = np.nan
            priors['rad_s'] = np.nan
            priors['rad_s_e'] = np.nan
            priors['mass_s'] = np.nan
            priors['mass_s_e'] = np.nan
            priors['period'] = np.nan
            priors['period_e'] = np.nan
            priors['duration'] = np.nan
            priors['duration_e'] = np.nan
            priors['depth'] = np.nan
            priors['depth_e'] = np.nan
        for keys in priors.keys():
            if priors[keys] != priors[keys]:
                priors[keys] = np.nan
        return priors
