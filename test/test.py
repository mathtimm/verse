import prose
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from prose import FitsManager
from prose import Sequence, blocks, viz
from os import path
#from prose import load
pd.options.mode.chained_assignment = None  # default='warn'
from verse import TFOPObservation

#obs = Observation(photometry.xarray.to_observation(photometry.stack.stack, sequence=photometry))
obs = TFOPObservation('/Users/mathildetimmermans/prose-env/TOIs/Giants_around_M-dwarfs/TOI-5278/artemis_20220629_TOI-5278_z.phot')

obs.auto_modeling(detrends = {"airmass":2})

from prose.reports import Report, Summary
from verse.reports import TransitModel, TESSNotes, TESSSummary

duration = float(obs.ttf_priors['jd_end']) - float(obs.ttf_priors['jd_start'])
t0 = 2450000 + float(obs.ttf_priors['jd_mid'])

# The latex pages
summary = TESSSummary(obs,expected=(t0,duration))
transitmodel = TransitModel(obs,expected=(t0,duration),transit=obs.opt['transit'], trend= obs.opt['systematics'],
                            posteriors=obs.posteriors,rms_bin=5/24/60)

notes = TESSNotes(obs,transitmodel)

# Make the full report
report = Report([summary,transitmodel,notes])
report.make(f"{obs.label}_report")