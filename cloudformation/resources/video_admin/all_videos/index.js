const AWS = require('aws-sdk');

AWS.config.update({region: 'us-east-1'});
const documentClient = new AWS.DynamoDB.DocumentClient();

const videoTable = process.env.VIDEO_TABLE;

exports.handler = async (event, context, callback) => {
    const {Items: items} = await documentClient.scan({TableName: videoTable}).promise();
    return {
        statusCode: '200',
        body: JSON.stringify({videos: items}),
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Max-Age': '86400',
        },
    };
};
