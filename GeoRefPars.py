# Georeferencing parameters to be used during these post-processing steps, including the GIS coordinate system, the resolution, and fusion parameters
def GeoRefPars():

    crs = 31966         # Spataial Reference System of LiDAR Data (EPSG code)
    # Fusion parameters for creating a gridded ground model (required for isolating canopy points)
    fusion_parameters = 'm m 1 12 2 2'
    # xyunits - Units for LIDAR data XY - M for meters, F for feet
    # zunits - Units for LIDAR data elevations - M for meters, F for feet
    # coordsys - Coordinate system for the surface - 0 for unknown, 1 for UTM, 2 for state plane
    # zone - Coordinate system zone for the surface (0 for unknown)
    # horizdatum - Horizontal datum for the surface - 0 for unknown, 1 for NAD27, 2 for NAD83
    # vertdatum - Vertical datum for the surface - 0 for unknown, 1 for NGVD29, 2 for NAVD88, 3 for GRS80
    cellsize = 1        # Cell Size
    
    return (crs, fusion_parameters, cellsize)
