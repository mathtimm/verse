# verse

 <b>verse</b> is an extension of the <b>prose</b> package for TESS follow-up observations and results reporting. 
 It gives access to additional features and properties specific to TESS Objects of Interest observations.  
A built-in function allows the user to model quickly the transit by making use of the <b>exoplanet</b> and <b>pymc3</b> packages and by retrieving priors directly from the TESS Transit Finder and the ExoFOP database.
<b>verse</b> creates observation reports and uploads the files directly onto ExoFOP for registered members of the TESS Follow-Up Observing Program (TFOP). 


## Usage

Loading an observation is done using the TFOPObservation class. It inherits all the methods and properties of the Observation class in <b>prose</b> and the analysis of the data is done following the [prose documentation](https://lgrcia.github.io/prose-docs). The priors extracted from the ExoFOP database and the TESS Transit Finder are easily accessed.

````python
obs = TFOPObservation('night_observation.phot')

obs.tic_id
obs.exofop_priors
obs.ttf_priors
````

The automatic modelling function uses the method of detrending based on polynomials of the systematics of the observation. The limb darkening coefficients can be retrieved from Claret 2012 or 2013 if the user chooses so. 

````python
obs.auto_modeling(detrends = {"airmass":2,"sky":2})
````

A report is made of three pages : a summary page with the results of the photometry, a transit model page with the results of the fit and a notes page with the summary of the observation and the elements requested by TFOP.  
Please keep in mind the notes page has to be manually edited for the summary sentence.
````python
summary = TESSSummary(obs,expected=(t0,duration))
transitmodel = TransitModel(obs,expected=(t0,duration),transit=obs.opt['transit'], trend= obs.opt['systematics'],
                            posteriors=obs.posteriors,rms_bin=5/24/60)
notes = TESSNotes(obs,transitmodel)

report = Report([summary,transitmodel,notes])
report.make(f"{obs.label}_report")

report.compile()
````

Once you are happy with the report, you will want to upload the results to ExoFOP and send an email to TFOP to share them with the community. 
````python
upload = UploadToExofop(obs,"night_observation_report",
                         delta_mag=0, transcov='Full',skip_file_upload=0,skip_summary_upload=0,toi='1234.01',username='username',
                          password = 'password',tag_number=1,print_responses=False)

upload.upload()

upload.email_title
````
## Installation
````
git clone https://github.com/mathtimm/verse 
````
Install in the same activated environment as <b>prose</b>.
````
pip install -e verse
````

## Main Developers
<i>[M. Timmermans](https://github.com/mathtimm) & <i>[L. García](https://github.com/LionelGarcia)

## Additional contributors 
<i>G. Dransfield</i> 



