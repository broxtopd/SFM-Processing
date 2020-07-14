library(lidR)
library(tools)
library(stringr)

# R Code to run the Cloth Simulation Filter (CSF; Zhang et al., 2016) algorithm to perform ground filtering
# See https://www.rdocumentation.org/packages/lidR/versions/2.2.5/topics/csf for CSF filter documentation
#
# Usage: RScript Filter_CSF.R <Input Cloud> <sloop_smooth> <class_threshold> <Suffix>
#
# Input Cloud: Path to input point cloud
# sloop_smooth: When steep slopes exist, set this parameter to TRUE to reduce errors during post-processing
# class_threshold: The distance to the simulated cloth to classify a point cloud into ground and non-ground
# Suffix: suffix to be added to the outputted las file (Warning, if set to "None", will overwrite the input file!)
#
# Created by Patrick Broxton
# Updated 6/30/2020

# Parse input arguments to the script
args = commandArgs(trailingOnly=TRUE)
infname = args[1]
sloop_smooth = args[2]
if (tolower(sloop_smooth) == "true") {
  sloop_smooth = TRUE
} else if (tolower(sloop_smooth) == "false") {
  sloop_smooth = FALSE
}
class_threshold = as.double(args[3])
out_suffix = args[4]

# Name the output file (depending on whether a suffix to be added)
if (out_suffix != "None") {
  ofname = paste0(str_remove(infname,  paste0('.',file_ext(infname))),'_',out_suffix,'.',file_ext(infname))
} else {
  ofname = infname
}

# Read point cloud file
lidardata  <- readLAS(infname)

# Perform CSF filter
lidardata  <- lasground(lidardata, csf(sloop_smooth = sloop_smooth,class_threshold = class_threshold))

# Only write out the ground returns
lidarsubset <- lasfilter(lidardata, Classification == 2L)
writeLAS(lidarsubset,ofname)