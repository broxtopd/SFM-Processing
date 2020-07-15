# SFM-Processing

This is a workflow to adjust SfM point clouds to match reference data. In this case, the reference data is a snow-off sfm point cloud, and
it is run for a sparsely forested domain about 1 ha in size.

Double click 'CorrectSnowOnSfMData.bat' to run the example workflow.  This will execute a series of scripts to perform the processing steps
(which are described below).  

To run these scripts, python and R should be installed (and accessable from the command line - e.g. on the system path if the provided 
batch files are to run properly).  Additionally, they require the US forest service's FUSION software
(http://forsys.cfr.washington.edu/fusion/fusionlatest.html), CloudCompare software (http://www.danielgm.net/cc/release/) and the GDAL utility
programs (https://gdal.org/download.html) to be installed and also on the system path.  Other dependencies in the python and R scripts are 
listed in the scripts, themselves, but most likely, the R LidR library, as well as the python gdal and possibly numpy libraries will need to 
be installed (e.g. using 'install.packages("LidR")' and 'pip install gdal').

## Workflow:

There are 5 steps included in this workflow (see the batch file for the syntax needed to execute the scripts used to run
the workflow, though detailed usage information for each script is included in the scripts, themselves).  

To demonstrate the effectiviness of this workflow, these point clouds are generated only using direct georeferencing information 
from the geotagged photos from which they are made (i.e. no GCPs), and thus have large vertical errors.  These point clouds were 
made in Agisoft Metashape software, and they have been pre-separated (using Metashape's built-in ground filtering), and thinned 
to reduce data size (using CloudCompare). 

The first step (accomplished by the CSF.R script) is to do additional ground filtering (using a Cloth Simulation Filter implemented
in R; because Agisoft's ground filter leaves a lot of debris on the ground surface).  

The second step (accomplished by the 'RemoveVerticalOffset.py' script) is to remove any large vertical offset between SfM and 
reference clouds (which tend to affect point clouds not generated using GCPs) by comparing the ground points in each set.  

The third step (accomplished by the 'ICP.py' script) is to use CloudCompare's Iterative Closest Point Algorithm to finely match the 
SfM and reference canopy models.  This step should be successful for point clouds where the georeferencing (following the preceeding 
step) is close (within a few meters), but there might need to be some manual adjustment before running this step if the georeferencing 
is particularly bad.  

The fourth and fifth steps are to correct for remaining tilt and potentially gentle warping in the SfM model (using the 'dewarp_model.py' script) 
using a low-order polynomial fit remove general distortion in the SfM point cloud.  First (step 4), remove tilting by applying a first 
order polynomial correction to the point clouds.  Then (step 5), remove any warping of the SfM data by applying a second order polynomial correction
to the point clouds.  If dealing with snow, this script needs to have a first guess snow depth map because it effectively clamps the 
SfM model to the reference model ground cloud (plus the first guess difference map).  In this case, this first guess map is generated from field sampling 
of snow depth and prior lidar data at this site

