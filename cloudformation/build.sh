#!/usr/bin/env bash

WORKING_DIRECTORY=$(pwd)
echo $WORKING_DIRECTORY

cd resources/video_encoding_engine/start_encode/
zip -r start_encode.zip index.py
mv start_encode.zip "$WORKING_DIRECTORY/output/"
cd $WORKING_DIRECTORY

cd resources/video_encoding_engine/request_encoding/
zip -r request_encoding.zip index.py
mv request_encoding.zip "$WORKING_DIRECTORY/output/"
cd $WORKING_DIRECTORY

cd resources/video_encoding_engine/update_encoding_state/
zip -r update_encoding_state.zip index.py
mv update_encoding_state.zip "$WORKING_DIRECTORY/output/"
cd $WORKING_DIRECTORY

cd resources/video_insights_engine/start_insights/
zip -r start_insights.zip index.py
mv start_insights.zip "$WORKING_DIRECTORY/output/"
cd $WORKING_DIRECTORY

cd resources/custom_resources_code/elastictranscoder/
yarn install
zip -r elastictranscoder.zip index.js node_modules/
mv elastictranscoder.zip "$WORKING_DIRECTORY/output/"
cd $WORKING_DIRECTORY
