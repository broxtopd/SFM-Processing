import sys, os, shutil
import subprocess
from osgeo import gdal
from osgeo.gdalconst import *
sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + '/../')
from GeoRefPars import GeoRefPars

# Uses CloudCompare's Iterative Closest Point (ICP) Algorithm to match a canopy point cloud with uncertain georeferncing with
# a refernce canopy point cloud (requires that the clouds match up reasonably closely in both the horizontal and vertical)
# See http://www.cloudcompare.org/doc/wiki/index.php?title=ICP for ICP filter documentation
#
# Usage: ICP.py <options> <Input Cloud> <Reference Cloud> <Suffix>
#
# Input Cloud: Path to input canopy point cloud
# Refernce Cloud: Path to the reference ground point cloud
# Suffix: suffix to be added to the outputted las file (Warning, if set to "None", will overwrite the input file!)
# Options: 
# -a, --additional_clouds: Specfies additional clouds (separated by commas) to perform the same adjustment for (for example, 
#       to adjust a point cloud containing ground points using the same adjustment that is applied to the canopy point cloud)
# 
# Note that in addition to the dependencies listed above, this code assumes that CloudCompare is installed and that it is 
# accessable via the command line (e.g. on the system path), as this script makes subprocess calls to its command line mode
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
    incloud_canopy = args[0]        # Input canopy point cloud
    ref_cloud_canopy = args[1]      # Bare earth canopy surface file
    out_suffix = args[2]        	# Output file suffix (for saved files)
    additional_clouds = options.additional_clouds
    
    # Check for the existance of the input and reference clouds
    path_errors = False
    if not os.path.exists(incloud_canopy):
        print('Error: ' + incloud_canopy + ' does not exist!')
        path_errors = True
    if not os.path.exists(ref_cloud_canopy):
        print('Error: ' + ref_cloud_canopy + ' does not exist!')
        path_errors = True
    if path_errors == True:
        sys.exit()
        
    # Name the output file (depending on whether a suffix to be added)
    if out_suffix == 'None':
        outcloud = incloud_canopy[:-4] + '.laz'
    else: 
        outcloud = incloud_canopy[:-4] + '_' + out_suffix + '.laz'
    
    # Perform CloudCompare's ICP Algorithm to match the input cloud to the reference cloud
    cmd = 'CloudCompare -SILENT -C_EXPORT_FMT LAS -AUTO_SAVE OFF -O -GLOBAL_SHIFT AUTO "' + incloud_canopy + '" -O -GLOBAL_SHIFT AUTO "' + ref_cloud_canopy + '" -ICP -FARTHEST_REMOVAL -POP_CLOUDS -SAVE_CLOUDS File "' + outcloud + '"'
    print(cmd)
    subprocess.call(cmd, shell=True)    
    
    # Apply the same adjustment to any additional point clouds
    if additional_clouds != None:
        AdditionalClouds = additional_clouds.split(',')
        
        # Find and read in the registration matrix file produced by the ICP algorithm
        for fname in os.listdir(os.path.dirname(incloud_canopy)): 
            if 'REGISTRATION_MATRIX' in fname:
                registration_matrix_file = os.path.dirname(incloud_canopy) + '/' + fname
                
        for incloud in AdditionalClouds:
            # If necissary, apply a suffix to these additional clouds
            if out_suffix == 'None':
                outcloud = incloud[:-4] + '.laz'
            else: 
                outcloud = incloud[:-4] + '_' + out_suffix + '.laz'
                
            # Apply the same transformation from the registration matrix file    
            cmd = 'CloudCompare -SILENT -C_EXPORT_FMT LAS -AUTO_SAVE OFF -O -GLOBAL_SHIFT AUTO "' + incloud + '" -APPLY_TRANS "' + registration_matrix_file + '" -SAVE_CLOUDS File "' + outcloud + '"'
            print(cmd)
            subprocess.call(cmd, shell=True)
    
    # Remove the registration matrix file
    os.remove(registration_matrix_file)