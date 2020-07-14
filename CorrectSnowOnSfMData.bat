REM Postprocess the snow-on point cloud

REM Perform ground filtering with cloth simulation filter (see Scripts\Filter_CSF.R for usage information)
REM Here, allow steep slope processing and set classification threshhold to 0.01 (for aggressive filtering)
RScript Scripts\Filter_CSF.R "Data\SnowOnSfMData\SnowOnGround.laz" TRUE 0.01 filtered

REM Remove any large vertical offset between SfM and reference point cloud
python Scripts\RemoveVerticalOffset.py -a "Data\SnowOnSfMData\SnowOnCanopy.laz" "Data\SnowOnSfMData\SnowOnGround_filtered.laz" "Data\SnowOffSfMData\SnowOffGround_filtered.laz" corrected

REM Use CloudCompare's Iterative Closest Point Algorithm to match the point clouds using the reference canopy points
python Scripts\ICP.py -a "Data\SnowOnSfMData\SnowOnGround_filtered_corrected.laz" "Data\SnowOnSfMData\SnowOnCanopy_corrected.laz" "Data\SnowOffSfMData\SnowOffCanopy.laz" None

REM Clamp the model to the ground surface (but first adding a first guess for snow thickness)
REM First, use a 1st order polynomial model to remove tilting in the model
python Scripts\dewarp_model.py -r -d "Data\FirstGuessSnowDepth\FirstGuess.tif" -a "Data\SnowOnSfMData\SnowOnCanopy_corrected.laz" "Data\SnowOnSfMData\SnowOnGround_filtered_corrected.laz" "Data\SnowOffSfMData\SnowOffGround_filtered.laz" 1 None

REM Next, use a 2nd order polynomial model to remove and warping in the model (such as dome or bowl effect)
python Scripts\dewarp_model.py -r -d "Data\FirstGuessSnowDepth\FirstGuess.tif" -a "Data\SnowOnSfMData\SnowOnCanopy_corrected.laz" "Data\SnowOnSfMData\SnowOnGround_filtered_corrected.laz" "Data\SnowOffSfMData\SnowOffGround_filtered.laz" 2 None
