import sys, os, shutil
import subprocess
from osgeo import ogr, osr, gdal
from osgeo.gdalconst import *
import tempfile
import itertools
import numpy as np
sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)) + '/../')
from GeoRefPars import GeoRefPars

# This script 'flattens' a Structure from Motion point (SfM) point cloud using a pre-existing bare-earth point cloud, and optionally, a first guess 
# difference map (in case the SfM data includes change from the original surface, e.g. when there is snow on the ground).  The code uses a low-order 
# polynomial fit remove general distortion in the SfM point cloud (e.g. caused by tilting or gentle warping).
#
#Usage: python dewarp_model.py <options> <Input Cloud> <Refernce Cloud> <Order> <Suffix>
#
# Input Cloud: Path to input ground point cloud
# Refernce Cloud: Path to the reference ground point cloud
# Order: Order of polynomial correcton
# Suffix: suffix to be added to the outputted las file (Warning, if set to "None", will overwrite the input file!)
# Options: 
# -a, --additional_clouds: Specfies additional clouds (separated by commas) to perform the same adjustment for (for example, 
#       to adjust a point cloud containing canopy points using the same adjustment that is applied to the ground point cloud)
# -d, --difference_map: incorporate a first guess differnece map to add to the reference ground surface before applying the 
#       polynomial corrections
# -r, --output_raster: Output a raster representing the final computed difference between the corrected input cloud and the 
#       reference cloud


# Read the georeferencing information and fusion parameters
(crs, fusion_parameters, cellsize) = GeoRefPars()

# Function to fit a polynomial model to a 2D raster
def polyfit2d(x, y, z, order):
    ncols = (order + 1)**2
    G = np.zeros((x.size, ncols))
    ij = itertools.product(range(order+1), range(order+1))
    for k, (i,j) in enumerate(ij):
        G[:,k] = x**i * y**j
    m, _, _, _ = np.linalg.lstsq(G, z,rcond=None)
    return m

# Function to evaluate a polynomial model on a 2D raster
def polyval2d(x, y, m):
    order = int(np.sqrt(len(m))) - 1
    ij = itertools.product(range(order+1), range(order+1))
    z = np.zeros_like(x)
    for a, (i,j) in zip(m, ij):
        z += a * x**i * y**j
    return z
	
# Optional parameters
def optparse_init():
    """Prepare the option parser for input (argv)"""

    from optparse import OptionParser, OptionGroup
    usage = 'Usage: %prog [options] input_file(s) [output]'
    p = OptionParser(usage)
    p.add_option('-d', '--difference_map', dest='difference_map', help='First guess snow depth map to add to the ground model') 
    p.add_option('-a', '--additional_clouds', dest='additional_clouds', help='Additional Clouds to apply the correction to')
    p.add_option('-r', '--output_raster', dest='output_raster', action='store_true')      # Output additional rasters showing shift and difference (1 m resolution)
    return p

if __name__ == '__main__':

    # Parse the command line arguments      
    argv = gdal.GeneralCmdLineProcessor( sys.argv ) 
    parser = optparse_init()
    options,args = parser.parse_args(args=argv[1:])
    incloud_ground = args[0]        # Input` ground point cloud
    ref_cloud_ground = args[1]      # Bare earth ground surface file
    order = int(args[2])            # Order of polynomial fit
    out_suffix = args[3]        	# Output file prefix (for saved files) 
    difference_map = options.difference_map
    additional_clouds = options.additional_clouds
    output_raster = options.output_raster
    
    # Check for the existance of the input and reference clouds
    path_errors = False
    if not os.path.exists(incloud_ground):
        print('Error: ' + incloud_ground + ' does not exist!')
        path_errors = True
    if not os.path.exists(ref_cloud_ground):
        print('Error: ' + ref_cloud_ground + ' does not exist!')
        path_errors = True
    if difference_map != None:
        if not os.path.exists(difference_map):
            print('Error: ' + difference_map + ' does not exist!')
            path_errors = True
    if additional_clouds != None:
        AdditionalClouds = additional_clouds.split(',')
        for incloud in AdditionalClouds:
            if not os.path.exists(incloud):
                print('Error: ' + incloud + ' does not exist!')
                path_errors = True   
    if path_errors == True:
        sys.exit()
    
    # Create a temporary working directory`
    working_dir = tempfile.mktemp()
    # working_dir = 'Working'
    if not os.path.exists(working_dir):
        os.makedirs(working_dir)
    
    # Create Surface files for the SFM ground point cloud in the temporary directory (using Fusion's GridSurfaceCreate program)
    cmd = 'GridSurfaceCreate "' + working_dir + '/surf.dtm" ' + str(cellsize) + ' ' + fusion_parameters + ' "' + incloud_ground + '"'
    print(cmd)
    subprocess.call(cmd, shell=True)
        
    # Convert from dtm format to asc format (so it can be read by gdal)
    cmd = 'DTM2ASCII "' + working_dir + '/surf.dtm" "' + working_dir + '/surf.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Assign georeferencing information using a gdal virtual raster layer
    cmd = 'gdalbuildvrt -a_srs "EPSG:' + str(crs) + '" "' + working_dir + '/surf.vrt" "' + working_dir + '/surf.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
        
    # Open the dataset
    inDs = gdal.Open(working_dir + '/surf.vrt')
    if inDs is None:
        print('Could not open ' + working_dir + '/surf.vrt')
        sys.exit(1)
        
    # Get raster characteristics
    wkt = inDs.GetProjection()
    s_srs = osr.SpatialReference()
    s_srs.ImportFromWkt(wkt)
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
    pc_ground_z = band.ReadAsArray()
    pc_ground_z[pc_ground_z == band.GetNoDataValue()] = np.nan
    
    # Create Surface files for the reference point cloud in the temporary directory (using Fusion's GridSurfaceCreate program)
    cmd = 'GridSurfaceCreate "' + working_dir + '/surf_reference.dtm" ' + str(cellsize) + ' ' + fusion_parameters + ' "' + ref_cloud_ground + '"'
    print(cmd)
    subprocess.call(cmd, shell=True)
        
    # Convert from dtm format to asc format (so it can be read by gdal)   
    cmd = 'DTM2ASCII "' + working_dir + '/surf_reference.dtm" "' + working_dir + '/surf_reference.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Assign georeferencing information using a gdal virtual raster layer
    tr = str(dx) + ' ' + str(dy)
    te = str(ulx) + ' ' + str(lry) + ' ' + str(lrx) + ' ' + str(uly)
    cmd = 'gdalbuildvrt -tr ' + tr + ' -te ' + te + ' -a_srs "EPSG:' + str(crs) + '" "' + working_dir + '/surf_reference.vrt" "' + working_dir + '/surf_reference.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Open the dataset
    inDs2 = gdal.Open(working_dir + '/surf_reference.vrt')
    if inDs2 is None:
        print('Could not open ' + working_dir + '/surf_reference.vrt')
        sys.exit(1)
        
    # Read the reference surface file
    band = inDs2.GetRasterBand(inDs2.RasterCount)    
    reference_z = band.ReadAsArray()
    reference_z[reference_z == band.GetNoDataValue()] = np.nan
    inDs2 = None
    
    # If specified, load the first guess difference map
    if difference_map != None:
        # Use gdal virtual raster layer to make sure that the extents / cellsize for the first guess difference map match the other data
        cmd = 'gdalbuildvrt -tr ' + tr + ' -te ' + te + ' -a_srs "EPSG:' + str(crs) + '" "' + working_dir + '/difference_map.vrt" "' + difference_map + '"'
        print(cmd)
        subprocess.call(cmd, shell=True)
    
        # Open the dataset
        inDs2 = gdal.Open(working_dir + '/difference_map.vrt')
        if inDs2 is None:
            print('Could not open ' + working_dir + '/difference_map.vrt')
            sys.exit(1)
            
        # Read the first guess difference map
        band = inDs2.GetRasterBand(inDs2.RasterCount)    
        difference = band.ReadAsArray()
        difference[difference == band.GetNoDataValue()] = np.nan
        inDs2 = None
    
    # Find the difference between the surfaces
    xx = np.linspace(ulx,lrx, width)
    yy = np.linspace(uly, lry, height)
    xx, yy = np.meshgrid(xx, yy)
    
    # Compute the actual corrections needed
    # If specified, add the first guess difference map
    if difference_map != None:
        zz = pc_ground_z - (reference_z + difference / 100)
    else:
        zz = pc_ground_z - reference_z
        
    xx = np.asarray(xx).reshape(-1)
    yy = np.asarray(yy).reshape(-1)
    zz = np.asarray(zz).reshape(-1)
    ii = np.isnan(zz)
    xx = xx[~ii]
    yy = yy[~ii]
    zz = zz[~ii]
    
    # Fit a 2d polynomial to model this difference (this will clamp the new surface to the existing ground model)
    m = polyfit2d(xx-ulx,yy-lry,zz,order)

    # Evaluate it on the original grid...
    xx = np.linspace(ulx, lrx, width)
    yy = np.linspace(uly, lry, height)
    xx, yy = np.meshgrid(xx, yy)
    zz = polyval2d(xx-ulx, yy-lry, m)
    
    # Compute the correction factor map
    # Note that ClipData program expects correction to be entirely positive, so we need a workaround to ensure that this condition is satisfied
    # We do so by adding a vertical offset to the correction factor map, and we will subtract this vertical offset using a "bias_elev" in ClipData
    vcorr = np.min(zz)-1
    corr = zz-vcorr
    
    # Output this correction factor map
    # Open the dataset
    driver = gdal.GetDriverByName("GTiff")
    outDs = driver.Create(working_dir + "/correction.tif", width, height, 1, GDT_Float32)
    if outDs is None:
        print('Could not create ' + working_dir + '/correction.tif')
        sys.exit(1)
        
    # Write the data
    outBand = outDs.GetRasterBand(1).WriteArray(corr, 0, 0)
    outDs.SetGeoTransform(inDs.GetGeoTransform())
    t_srs = osr.SpatialReference()
    t_srs.ImportFromEPSG(crs)
    outDs.SetProjection(t_srs.ExportToWkt())
    outDs = None
    inDs = None
    print('Created ' + working_dir + '/correction.tif')
    
    # Convert the correction factor map to fusion compatible dataset
    # First, through a .asc file
    cmd = 'gdal_translate -of AAIGrid "' + working_dir + '/correction.tif" "' + working_dir + '/correction.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Then, create a .dtm file from it
    cmd = 'ASCII2DTM "' + working_dir + '/correction.dtm" ' + fusion_parameters + ' "' + working_dir + '/correction.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    # Convert the correction factor map to a format that can be operated on by FUSION
    cmd = 'ASCII2DTM "' + working_dir + '/correction.dtm" ' + fusion_parameters + ' "' + working_dir + '/correction.asc"'
    print(cmd)
    subprocess.call(cmd, shell=True)
    
    
    # Name the output cloud (depending on whether a suffix to be added)
    incloud_ground_i = incloud_ground   # Need this for naming the output raster below
    if out_suffix == 'None':
        # If the outcloud and incloud are the same, rename the input file (because FUSION won't overwrite files)
        outcloud = incloud_ground[:-4] + '.laz'
        os.rename(incloud_ground,incloud_ground[:-4] + '_tmp.laz')
        incloud_ground = incloud_ground[:-4] + '_tmp.laz'
    else: 
        outcloud = incloud_ground[:-4] + '_' + out_suffix + '.laz'
        
    # Perform the correction (using FUSION's ClipData program)
    cmd = 'ClipData /height /dtm:"' + working_dir + '/correction.dtm" /biaselev:' + str(-vcorr) + ' "' + incloud_ground + '" "' + outcloud + '" ' + str(ulx+1) + ' ' + str(lry+1) + ' ' + str(lrx-1) + ' ' + str(uly-1)
    print(cmd)
    subprocess.call(cmd, shell=True)    
    
    # If the input cloud is to be overwritten, then remove the renamed (from above) input cloud
    if out_suffix == 'None':
        os.remove(incloud_ground)
    
    # Apply the same correction to any additional point clouds
    if additional_clouds != None:
        AdditionalClouds = additional_clouds.split(',')
        
        for incloud in AdditionalClouds:
            # If necissary, apply a suffix to these additional clouds
            if out_suffix == 'None':
                outcloud = incloud[:-4] + '.laz'
                os.rename(incloud,incloud[:-4] + '_tmp.laz')
                incloud = incloud[:-4] + '_tmp.laz'
            else: 
                outcloud = incloud[:-4] + '_' + out_suffix + '.laz'
                
            # Apply the same transformation to each additional cloud
            cmd = 'clipdata /height /dtm:"' + working_dir + '/correction.dtm" /biaselev:' + str(-vcorr) + ' "' + incloud + '" "' + outcloud + '" ' + str(ulx+1) + ' ' + str(lry+1) + ' ' + str(lrx-1) + ' ' + str(uly-1)
            print(cmd)
            subprocess.call(cmd, shell=True)  
            
            # If the input cloud is to be overwritten, then remove the renamed (from above) input cloud
            if out_suffix == 'None':
                os.remove(incloud)
    
    # If specified, output the difference raster
    if output_raster == True: 
    
        # Compute the difference between the input cloud (minus the correction)
        diff = (pc_ground_z - zz)-reference_z 
    
        # Name the output raster (depending on whether a suffix to be added)
        if out_suffix == "None":
            outraster_change = incloud_ground_i[:-4] + '_diff.tif'
        else:
            outraster_change = incloud_ground_i[:-4] + '_' + out_suffix + '_diff.tif'
        
        # Write the difference raster (using the same georeferencing information as the temporary correction file)
        inFile = working_dir + '/correction.tif'
        ds = gdal.Open(inFile)
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray()
        [cols, rows] = arr.shape
        
        # Write the data
        driver = gdal.GetDriverByName("GTiff")
        outdata = driver.Create(outraster_change, rows, cols, 1, gdal.GDT_Float32)
        outdata.SetGeoTransform(ds.GetGeoTransform())
        outdata.SetProjection(ds.GetProjection())
        outdata.GetRasterBand(1).WriteArray(diff*100)   # Convert to centimeters
        outdata.GetRasterBand(1).SetNoDataValue(-9999)
        outdata.FlushCache()
        outdata = None
        ds=None
    
    # Remove the temporary directory (including any orphaned files)
    if os.path.exists(working_dir):
      shutil.rmtree(working_dir)
        
        
