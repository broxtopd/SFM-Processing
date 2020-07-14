import sys, os, shutil
import subprocess
from osgeo import gdal
from osgeo.gdalconst import *
import tempfile
import numpy as np
sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + '/../')
from GeoRefPars import GeoRefPars

# Removes vertical offset for an for a ground point cloud with uncertain georeferncing by comparing its elevation with
# that from reference ground point cloud (requires that the clouds match up reasonably closely in the horizontal)
#
# Usage: RemoveVerticalOffset.py <options> <Input Cloud> <Reference Cloud> <Suffix>
#
# Input Cloud: Path to input ground point cloud
# Refernce Cloud: Path to the reference ground point cloud
# Suffix: suffix to be added to the outputted las file (Warning, if set to "None", will overwrite the input file!)
# Options: 
# -a, --additional_clouds: Specfies additional clouds (separated by commas) to perform the same adjustment for (for example, 
#       to adjust a point cloud containing canopy points using the same adjustment that is applied to the ground point cloud)
# 
# Note that in addition to the dependencies listed above, this code assumes that the gdal and Fusion command line tools are 
# installed and are accessable via the command line (e.g. on the system path), as this script makes subprocess calls to them
#
# Created by Patrick Broxton
# Updated 6/30/2020

# Read the georeferencing information and fusion parameters
(crs, fusion_parameters, cellsize) = GeoRefPars()

# Optional parameters
def optparse_init():
    """Prepare the option parser for input (argv)"""

    from optparse import OptionParser, OptionGroup
    usage = 'Usage: %prog [options] input_file(s) [output]'
    p = OptionParser(usage)
    p.add_option('-a', '--additional_clouds', dest='additional_clouds', help='Additional clouds to apply the correction to')
    return p
    
if __name__ == '__main__':

    # Parse the command line arguments      
    argv = gdal.GeneralCmdLineProcessor( sys.argv ) 
    parser = optparse_init()
    options,args = parser.parse_args(args=argv[1:])
    incloud_ground = args[0]        # Input ground point cloud
    ref_cloud_ground = args[1]      # Reference ground surface file
    out_suffix = args[2]        	# Output file suffix (for saved files)
    additional_clouds = options.additional_clouds
    
    # Check for the existance of the input and reference clouds
    path_errors = False
    if not os.path.exists(incloud_ground):
        print('Error: ' + incloud_ground + ' does not exist!')
        path_errors = True
    if not os.path.exists(ref_cloud_ground):
        print('Error: ' + ref_cloud_ground + ' does not exist!')
        path_errors = True 
    if path_errors == True:
        sys.exit()
        
    # Create a temporary working directory`
    working_dir = tempfile.mktemp()
    if not os.path.exists(working_dir):
        os.makedirs(working_dir)
        
    # Create Surface files for the SFM ground point cloud in the temporary directory (using Fusion's GridSurfaceCreate program)
    cmd = 'GridSurfaceCreate "' + working_dir + '/surf_sfm.dtm" ' + str(cellsize) + ' ' + fusion_parameters + ' "' + incloud_ground + '"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Convert from dtm format to asc format (so it can be read by gdal)
    cmd = 'DTM2ASCII "' + working_dir + '/surf_sfm.dtm" "' + working_dir + '/surf_sfm.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Assign georeferencing information using a gdal virtual raster layer
    cmd = 'gdalbuildvrt -a_srs "EPSG:' + str(crs) + '" "' + working_dir + '/surf_sfm.vrt" "' + working_dir + '/surf_sfm.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)

    # Open the dataset
    inDs = gdal.Open(working_dir + '/surf_sfm.vrt')
    if inDs is None:
        print('Could not open ' + working_dir + '/surf_sfm.vrt')
        sys.exit(1)
    
    # Get raster characteristics
    width = inDs.RasterXSize
    height = inDs.RasterYSize
    gt = inDs.GetGeoTransform()
    ulx = gt[0]
    lry = gt[3] + width*gt[4] + height*gt[5] 
    lrx = gt[0] + width*gt[1] + height*gt[2]
    uly = gt[3] 
    dx = gt[1]
    dy = -gt[5]
    
    # Read the ground surface file
    band = inDs.GetRasterBand(inDs.RasterCount)    
    sfm_z = band.ReadAsArray()
    sfm_z[sfm_z == band.GetNoDataValue()] = np.nan
    inDs = None
    
    # Create Surface files for the reference point cloud in the temporary directory (using Fusion's GridSurfaceCreate program)
    cmd = 'GridSurfaceCreate "' + working_dir + '/surf_lidar.dtm" ' + str(cellsize) + ' ' + fusion_parameters + ' "' + ref_cloud_ground + '"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Convert from dtm format to asc format (so it can be read by gdal)    
    cmd = 'DTM2ASCII "' + working_dir + '/surf_lidar.dtm" "' + working_dir + '/surf_lidar.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Assign georeferencing information using a gdal virtual raster layer
    te_str = str(ulx) + ' ' + str(lry) + ' ' + str(lrx) + ' ' + str(uly)
    cmd = 'gdalbuildvrt -te ' + te_str + ' -a_srs "EPSG:' + str(crs) + '" "' + working_dir + '/surf_lidar.vrt" "' + working_dir + '/surf_lidar.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Open the dataset
    inDs2 = gdal.Open(working_dir + '/surf_lidar.vrt')
    if inDs2 is None:
        print('Could not open ' + working_dir + '/surf_lidar.vrt')
        sys.exit(1)
    
    # Read the reference cloud
    band = inDs2.GetRasterBand(inDs2.RasterCount)    
    lidar_z = band.ReadAsArray()
    lidar_z[lidar_z == band.GetNoDataValue()] = np.nan
    inDs2 = None
    
    # Figure out the average difference
    diff = sfm_z - lidar_z
    vcorr = np.nanmean(diff)
    
    # Name the output file (depending on whether a suffix to be added)
    if out_suffix == 'None':
        outcloud = incloud_ground[:-4] + '.laz'
    else: 
        outcloud = incloud_ground[:-4] + '_' + out_suffix + '.laz'
        
    # Apply the vertical offset to the input point cloud (using Fusion's clipdata program)
    cmd = 'clipdata /height /biaselev:' + str(-vcorr) + ' "' + incloud_ground + '" "' + outcloud + '" ' + str(ulx) + ' ' + str(lry) + ' ' + str(lrx) + ' ' + str(uly)
    print(cmd)
    subprocess.call(cmd, shell=True)    
    
    # Apply the same vertical offset to any additional point clouds
    if additional_clouds != None:
        AdditionalClouds = additional_clouds.split(',')
        
        for incloud in AdditionalClouds:
            # If necissary, apply a suffix to these additional clouds
            if out_suffix == 'None':
                outcloud = incloud[:-4] + '.laz'
            else: 
                outcloud = incloud[:-4] + '_' + out_suffix + '.laz'
                
            # Apply the vertical offset to each additional cloud
            cmd = 'clipdata /height  /biaselev:' + str(-vcorr) + ' "' + incloud + '" "' + outcloud + '" ' + str(ulx) + ' ' + str(lry) + ' ' + str(lrx) + ' ' + str(uly)
            print(cmd)
            subprocess.call(cmd, shell=True)
    
    # Remove the temporary directory (including any orphaned files)
    if os.path.exists(working_dir):
       shutil.rmtree(working_dir)