import json

from troposphere import Template, AWS_STACK_NAME, Ref, ImportValue, GetAtt, Join, Parameter, constants, AWS_REGION, iam, \
    AWSHelperFn, awslambda
from troposphere.apigateway import RestApi, EndpointConfiguration, Resource, Method, Integration, MethodResponse, Model, \
    IntegrationResponse, Deployment, Stage, ApiKey, StageKey, UsagePlan, QuotaSettings, ApiStage, UsagePlanKey, \
    ThrottleSettings
from troposphere.awslambda import Code, Environment, TracingConfig, EventSourceMapping
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.cloudfront import Distribution, DistributionConfig, DefaultCacheBehavior, ViewerCertificate, \
    ForwardedValues, Origin, CustomOriginConfig, OriginCustomHeader, CacheBehavior, LambdaFunctionAssociation
from troposphere.dynamodb import Table, AttributeDefinition, KeySchema, GlobalSecondaryIndex, Projection
from troposphere.iam import Role
from troposphere.logs import LogGroup
from troposphere.route53 import RecordSetGroup, RecordSet, AliasTarget
from troposphere.serverless import Function, S3Location


class VersionRef(AWSHelperFn):
    def __init__(self, data):
        func = self.getdata(data)
        self.data = {'Ref': "{function}.Version".format(function=func)}


stage_name = 'v1'
api_key_secret = 'yeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeet'

UPLOAD_BUCKET = 'spunt-video-encoding-engine-upload'

template = Template(Description='API for spunt.be')
template.set_transform('AWS::Serverless-2016-10-31')

dns_stack = template.add_parameter(Parameter(
    'DnsStack',
    Type=constants.STRING,
    Default='spunt-punt-be-dns',
))

core_stack = template.add_parameter(Parameter(
    'CoreStack',
    Type=constants.STRING,
    Default='spunt-core',
))

domain_name = template.add_parameter(Parameter(
    'DomainName',
    Type=constants.STRING,
    Default='api.spunt.be',
))

all_videos_lambda_code_key = template.add_parameter(Parameter(
    'AllVideos',
    Type=constants.STRING,
    Default='lambda-code/api/all_videos.zip',
))

trending_videos_lambda_code_key = template.add_parameter(Parameter(
    'TrendingVideos',
    Type=constants.STRING,
    Default='lambda-code/api/trending_videos.zip',
))

hot_videos_lambda_code_key = template.add_parameter(Parameter(
    'HotVideos',
    Type=constants.STRING,
    Default='lambda-code/api/hot_videos.zip',
))

recommended_videos_lambda_code_key = template.add_parameter(Parameter(
    'Recommended',
    Type=constants.STRING,
    Default='lambda-code/api/recommended_videos.zip',
))

get_video_lambda_code_key = template.add_parameter(Parameter(
    'GetVideo',
    Type=constants.STRING,
    Default='lambda-code/api/get_video.zip',
))

rewrite_downvote_lambda_code_key = template.add_parameter(Parameter(
    'RewriteDownvote',
    Type=constants.STRING,
    Default='lambda-code/api/rewrite_downvote.zip',
))

consume_events_code_key = template.add_parameter(Parameter(
    'ConsumeEvents',
    Type=constants.STRING,
    Default='lambda-code/api/consume_events.zip',
))

upvote_lambda_code_key = template.add_parameter(Parameter(
    'Upvote',
    Type=constants.STRING,
    Default='lambda-code/api/upvote.zip',
))

upload_lambda_code_key = template.add_parameter(Parameter(
    'Upload',
    Type=constants.STRING,
    Default='lambda-code/api/upload.zip',
))

template.add_parameter_to_group(all_videos_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(trending_videos_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(hot_videos_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(recommended_videos_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(get_video_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(rewrite_downvote_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(consume_events_code_key, 'Lambda Keys')
template.add_parameter_to_group(upvote_lambda_code_key, 'Lambda Keys')
template.add_parameter_to_group(upload_lambda_code_key, 'Lambda Keys')

video_table = template.add_resource(Table(
    'VideoTable',
    BillingMode='PAY_PER_REQUEST',
    AttributeDefinitions=[AttributeDefinition(
        AttributeName='videoId',
        AttributeType='S',
    ), AttributeDefinition(
        AttributeName='lastModified',
        AttributeType='S',
    ), AttributeDefinition(
        AttributeName='videoState',
        AttributeType='S',
    ), AttributeDefinition(
        AttributeName='upvotes',
        AttributeType='N',
    )],
    KeySchema=[KeySchema(
        AttributeName='videoId',
        KeyType='HASH',
    )],
    GlobalSecondaryIndexes=[GlobalSecondaryIndex(
        IndexName='lastModifiedInState',
        KeySchema=[KeySchema(
            AttributeName='videoState',
            KeyType='HASH',
        ), KeySchema(
            AttributeName='lastModified',
            KeyType='RANGE',
        )],
        Projection=Projection(
            ProjectionType='ALL',
        ),
    ), GlobalSecondaryIndex(
        IndexName='upvotedInState',
        KeySchema=[KeySchema(
            AttributeName='videoState',
            KeyType='HASH',
        ), KeySchema(
            AttributeName='upvotes',
            KeyType='RANGE',
        )],
        Projection=Projection(
            ProjectionType='ALL',
        ),
    )]
))

consume_events_role = template.add_resource(Role(
    'ConsumeEventsRole',
    Path="/",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": ["sts:AssumeRole"],
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com"]},
        }],
    },
    ManagedPolicyArns=[
        ImportValue(Join('-', [Ref(core_stack), 'LambdaDefaultPolicy', 'Arn'])),
        ImportValue(Join('-', [Ref(core_stack), 'EventsToApiQueuePolicy', 'Arn']))
    ],
    Policies=[iam.Policy(
        PolicyName="api-consume-events",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Action": ["dynamodb:UpdateItem"],
                "Resource": [GetAtt(video_table, 'Arn')],
                "Effect": "Allow",
            }],
        })],
))

consume_events_function = template.add_resource(awslambda.Function(
    'ConsumeEventsFunction',
    Description='Consumes events to build the video model.',
    Runtime='python3.7',
    Handler='index.handler',
    Role=GetAtt(consume_events_role, 'Arn'),
    Code=Code(
        S3Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        S3Key=Ref(consume_events_code_key),
    ),
    Environment=Environment(
        Variables={
            'VIDEO_TABLE': Ref(video_table),
        }
    ),
    TracingConfig=TracingConfig(
        Mode='Active',
    ),
))

template.add_resource(LogGroup(
    "ConsumeEventsLogGroup",
    LogGroupName=Join('/', ['/aws/lambda', Ref(consume_events_function)]),
    RetentionInDays=7,
))

template.add_resource(EventSourceMapping(
    'InvokeConsumeEvents',
    EventSourceArn=ImportValue(Join('-', [Ref(core_stack), 'EventsToApiQueue-Arn'])),
    FunctionName=Ref(consume_events_function),
    Enabled=True,
))

cloudfront_certificate = template.add_resource(Certificate(
    "CloudFrontCertificate",
    DomainName=Ref(domain_name),
    DomainValidationOptions=[DomainValidationOption(
        DomainName=Ref(domain_name),
        ValidationDomain=ImportValue(Join('-', [Ref(dns_stack), 'HostedZoneName'])),
    )],
    ValidationMethod='DNS',
))

api_gateway = template.add_resource(RestApi(
    'ApiGateway',
    Name=Ref(AWS_STACK_NAME),
    Description='REST API to handle requests that fall through lambda @ edge.',
    EndpointConfiguration=EndpointConfiguration(
        Types=['REGIONAL'],
    )
))

health_resource = template.add_resource(Resource(
    'HealthResource',
    RestApiId=Ref(api_gateway),
    PathPart="health",
    ParentId=GetAtt(api_gateway, "RootResourceId"),
))

upvote_resource = template.add_resource(Resource(
    'UpvoteResource',
    RestApiId=Ref(api_gateway),
    PathPart="upvote",
    ParentId=GetAtt(api_gateway, "RootResourceId"),
))

upload_resource = template.add_resource(Resource(
    'UploadResource',
    RestApiId=Ref(api_gateway),
    PathPart="upload",
    ParentId=GetAtt(api_gateway, "RootResourceId"),
))

health_model = template.add_resource(Model(
    'HealthModel',
    ContentType='application/json',
    RestApiId=Ref(api_gateway),
    Schema={
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "HealthModel",
        "type": "object",
        "properties": {
            "message": {
                "type": "string"
            },
        }
    },
))

health_method = template.add_resource(Method(
    "HealthMethod",
    ApiKeyRequired=True,
    RestApiId=Ref(api_gateway),
    AuthorizationType="NONE",
    ResourceId=Ref(health_resource),
    HttpMethod="GET",
    OperationName='mock',
    Integration=Integration(
        Type='MOCK',
        IntegrationResponses=[IntegrationResponse(
            ResponseTemplates={
                'application/json': "{\"message\": \"OK\"}"
            },
            StatusCode='200'
        )],
        PassthroughBehavior='WHEN_NO_TEMPLATES',
        RequestTemplates={
            'application/json': "{\"statusCode\": 200, \"message\": \"OK\"}"
        },
    ),
    MethodResponses=[
        MethodResponse(
            'HealthResponse',
            ResponseModels={
                'application/json': Ref(health_model),
            },
            StatusCode='200',
        )
    ],
))

# This should be done with a mock method with mocked response headers. But I just want it to work right now.
options_role = template.add_resource(Role(
    'OptionsRole',
    Path="/",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": ["sts:AssumeRole"],
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com", "apigateway.amazonaws.com"]},
        }],
    },
    ManagedPolicyArns=[
        ImportValue(Join('-', [Ref(core_stack), 'LambdaDefaultPolicy', 'Arn'])),
    ],
    Policies=[iam.Policy(
        PolicyName="api-invoke-lambda",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Action": ['lambda:InvokeFunction'],
                "Resource": '*',
                "Effect": "Allow",
            }],
        })],
))

with open('resources/spunt_api/options/index.py', 'r') as lambda_code:
    options_function = template.add_resource(Function(
        'OptionsFunction',
        Description='Returns response with CORS headers for everyone.',
        Runtime='python3.7',
        Handler='index.handler',
        Role=GetAtt(options_role, 'Arn'),
        InlineCode=lambda_code.read(),
    ))

template.add_resource(LogGroup(
    "OptionsFunctionLogGroup",
    LogGroupName=Join('/', ['/aws/lambda', Ref(options_function)]),
    RetentionInDays=7,
))

upvote_role = template.add_resource(Role(
    'UpvoteRole',
    Path="/",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": ["sts:AssumeRole"],
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com", "apigateway.amazonaws.com"]},
        }],
    },
    ManagedPolicyArns=[
        ImportValue(Join('-', [Ref(core_stack), 'LambdaDefaultPolicy', 'Arn'])),
    ],
    Policies=[iam.Policy(
        PolicyName="api-invoke-lambda",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Action": ['lambda:InvokeFunction'],
                "Resource": '*',
                "Effect": "Allow",
            }],
        })],
))

upvote_function = template.add_resource(Function(
    'UpvoteFunction',
    Description='Creates an upvote event.',
    Runtime='python3.7',
    Handler='index.handler',
    Role=GetAtt(upvote_role, 'Arn'),
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(upvote_lambda_code_key),
    ),
    Environment=Environment(
        Variables={
            'VIDEO_EVENTS_TABLE': ImportValue(Join('-', [Ref(core_stack), 'VideoEventsTable', 'Ref'])),
        }
    )
))

template.add_resource(LogGroup(
    "UpvoteFunctionLogGroup",
    LogGroupName=Join('/', ['/aws/lambda', Ref(upvote_function)]),
    RetentionInDays=7,
))

upvote_method = template.add_resource(Method(
    "UpvoteMethod",
    ApiKeyRequired=True,
    RestApiId=Ref(api_gateway),
    AuthorizationType="NONE",
    ResourceId=Ref(upvote_resource),
    HttpMethod="POST",
    Integration=Integration(
        Credentials=GetAtt(upvote_role, "Arn"),
        Type="AWS_PROXY",
        IntegrationHttpMethod='POST',
        IntegrationResponses=[
            IntegrationResponse(
                StatusCode='200'
            )
        ],
        Uri=Join("", [
            "arn:aws:apigateway:", Ref(AWS_REGION), ":lambda:path/2015-03-31/functions/",
            GetAtt(upvote_function, "Arn"),
            "/invocations"
        ])
    ),
    MethodResponses=[
        MethodResponse(
            "UpvoteResponse",
            StatusCode='200'
        )
    ]
))

upvote_options_method = template.add_resource(Method(
    "UpvoteOptionsMethod",
    ApiKeyRequired=False,
    RestApiId=Ref(api_gateway),
    AuthorizationType="NONE",
    ResourceId=Ref(upvote_resource),
    HttpMethod="OPTIONS",
    Integration=Integration(
        Credentials=GetAtt(options_role, "Arn"),
        Type="AWS_PROXY",
        IntegrationHttpMethod='POST',
        IntegrationResponses=[
            IntegrationResponse(
                StatusCode='200'
            )
        ],
        Uri=Join("", [
            "arn:aws:apigateway:", Ref(AWS_REGION), ":lambda:path/2015-03-31/functions/",
            GetAtt(options_function, "Arn"),
            "/invocations"
        ])
    ),
    MethodResponses=[
        MethodResponse(
            "OptionsResponse",
            StatusCode='200'
        )
    ]
))

upload_role = template.add_resource(Role(
    'UploadRole',
    Path="/",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": ["sts:AssumeRole"],
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com", "apigateway.amazonaws.com"]},
        }],
    },
    ManagedPolicyArns=[
        ImportValue(Join('-', [Ref(core_stack), 'LambdaDefaultPolicy', 'Arn'])),
    ],
    Policies=[iam.Policy(
        PolicyName="api-invoke-lambda",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Action": ['lambda:InvokeFunction'],
                "Resource": '*',
                "Effect": "Allow",
            }, {
                "Action": ['s3:PutObject'],
                "Resource": [
                    Join('', ['arn:aws:s3:::', UPLOAD_BUCKET, '/*'])
                ],
                "Effect": "Allow",
            }],
        })],
))

upload_function = template.add_resource(Function(
    'UploadFunction',
    Description='Creates a new video event.',
    Runtime='python3.7',
    Handler='index.handler',
    Role=GetAtt(upload_role, 'Arn'),
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(upload_lambda_code_key),
    ),
    Environment=Environment(
        Variables={
            'VIDEO_EVENTS_TABLE': ImportValue(Join('-', [Ref(core_stack), 'VideoEventsTable', 'Ref'])),
        }
    )
))

template.add_resource(LogGroup(
    "UploadFunctionLogGroup",
    LogGroupName=Join('/', ['/aws/lambda', Ref(upload_function)]),
    RetentionInDays=7,
))

upload_method = template.add_resource(Method(
    "UploadMethod",
    ApiKeyRequired=True,
    RestApiId=Ref(api_gateway),
    AuthorizationType="NONE",
    ResourceId=Ref(upload_resource),
    HttpMethod="POST",
    Integration=Integration(
        Credentials=GetAtt(upvote_role, "Arn"),
        Type="AWS_PROXY",
        IntegrationHttpMethod='POST',
        IntegrationResponses=[
            IntegrationResponse(
                StatusCode='200'
            )
        ],
        Uri=Join("", [
            "arn:aws:apigateway:", Ref(AWS_REGION), ":lambda:path/2015-03-31/functions/",
            GetAtt(upload_function, "Arn"),
            "/invocations"
        ])
    ),
    MethodResponses=[
        MethodResponse(
            "UploadResponse",
            StatusCode='200'
        )
    ]
))

upload_options_method = template.add_resource(Method(
    "UploadOptionsMethod",
    ApiKeyRequired=False,
    RestApiId=Ref(api_gateway),
    AuthorizationType="NONE",
    ResourceId=Ref(upload_resource),
    HttpMethod="OPTIONS",
    Integration=Integration(
        Credentials=GetAtt(options_role, "Arn"),
        Type="AWS_PROXY",
        IntegrationHttpMethod='POST',
        IntegrationResponses=[
            IntegrationResponse(
                StatusCode='200'
            )
        ],
        Uri=Join("", [
            "arn:aws:apigateway:", Ref(AWS_REGION), ":lambda:path/2015-03-31/functions/",
            GetAtt(options_function, "Arn"),
            "/invocations"
        ])
    ),
    MethodResponses=[
        MethodResponse(
            "OptionsResponse",
            StatusCode='200'
        )
    ]
))

deployment = template.add_resource(Deployment(
    "Deployment" + stage_name,
    DependsOn=health_method,
    RestApiId=Ref(api_gateway),
))

stage = template.add_resource(Stage(
    'Stage' + stage_name,
    StageName=stage_name,
    RestApiId=Ref(api_gateway),
    DeploymentId=Ref(deployment),
))

key = template.add_resource(ApiKey(
    "ApiKey",
    Enabled=True,
    Value=api_key_secret,
    StageKeys=[StageKey(
        RestApiId=Ref(api_gateway),
        StageName=Ref(stage),
    )],
))

usagePlan = template.add_resource(UsagePlan(
    "UsagePlan",
    UsagePlanName="UsagePlan",
    Description="Usage plan for small amount of requests not handles by lambda @ edge.",
    Quota=QuotaSettings(
        Limit=1000,
        Period="MONTH",
    ),
    Throttle=ThrottleSettings(
        RateLimit=50,
        BurstLimit=200,
    ),
    ApiStages=[
        ApiStage(
            ApiId=Ref(api_gateway),
            Stage=Ref(stage),
        )],
))

usagePlanKey = template.add_resource(UsagePlanKey(
    "UsagePlanKey",
    KeyId=Ref(key),
    KeyType="API_KEY",
    UsagePlanId=Ref(usagePlan),
))

readonly_function_role = template.add_resource(Role(
    'ReadonlyVideoApiRole',
    Path="/",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": ["sts:AssumeRole"],
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com", "edgelambda.amazonaws.com"]},
        }],
    },
    Policies=[iam.Policy(
        PolicyName="video-api-readonly",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Action": ['logs:CreateLogGroup', "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "arn:aws:logs:*:*:*",
                "Effect": "Allow",
            }, {
                "Action": ['dynamodb:Query', 'dynamodb:GetItem'],
                "Resource": [GetAtt(video_table, 'Arn'), Join('', [GetAtt(video_table, 'Arn'), '/*'])],
                "Effect": "Allow",
            }],
        })],
))

all_videos_function = template.add_resource(Function(
    'AllVideosFunction',
    Description='Returns list of random videos.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(all_videos_lambda_code_key),
    ),
))

trending_videos_function = template.add_resource(Function(
    'TrendingVideosFunction',
    Description='Returns list of videos that will become hot, based on Forecast.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(trending_videos_lambda_code_key),
    ),
))

hot_videos_function = template.add_resource(Function(
    'HotVideosFunction',
    Description='Returns list of videos that have a lot of upvotes in the last x hours.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(hot_videos_lambda_code_key),
    ),
))

recommended_videos_function = template.add_resource(Function(
    'RecommendedVideosFunction',
    Description='Returns list videos recommended for the user, based on Personalize.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(recommended_videos_lambda_code_key),
    ),
))

get_video_function = template.add_resource(Function(
    'GetVideoFunction',
    Description='Returns single video.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(get_video_lambda_code_key),
    ),
))

rewrite_downvote_function = template.add_resource(Function(
    'RewriteDownvoteFunction',
    Description='Rewrite /v1/downvote to /v1/upvote.',
    Runtime='nodejs10.x',
    Handler='index.handler',
    Role=GetAtt(readonly_function_role, 'Arn'),
    AutoPublishAlias='live',
    CodeUri=S3Location(
        Bucket=ImportValue(Join('-', [Ref(core_stack), 'LambdaCodeBucket-Ref'])),
        Key=Ref(rewrite_downvote_lambda_code_key),
    ),
))

api_cdn = template.add_resource(Distribution(
    "ApiDistribution",
    DistributionConfig=DistributionConfig(
        Aliases=[Ref(domain_name)],
        Comment=Ref(AWS_STACK_NAME),
        DefaultCacheBehavior=DefaultCacheBehavior(
            TargetOriginId='apigateway',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
        ),
        CacheBehaviors=[CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/videos/all',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(all_videos_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/videos/trending',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(trending_videos_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/videos/hot',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(hot_videos_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/videos/recommendations',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(recommended_videos_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/video/*',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            MinTTL=120,  # 2 minutes
            DefaultTTL=300,  # 5 minutes
            MaxTTL=300,  # 5 minutes
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(get_video_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/v1/downvote',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            Compress=True,
            LambdaFunctionAssociations=[LambdaFunctionAssociation(
                EventType='origin-request',
                LambdaFunctionARN=VersionRef(rewrite_downvote_function),
            )],
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/v1/upvote',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            Compress=True,
        ), CacheBehavior(
            TargetOriginId="apigateway",
            PathPattern='/v1/upload',
            ViewerProtocolPolicy='redirect-to-https',
            AllowedMethods=['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
            CachedMethods=['GET', 'HEAD', 'OPTIONS'],
            ForwardedValues=ForwardedValues(
                QueryString=False,
            ),
            Compress=True,
        )],
        Enabled=True,
        HttpVersion='http2',
        IPV6Enabled=True,
        Origins=[Origin(
            Id='apigateway',
            DomainName=Join("", [Ref(api_gateway), ".execute-api.", Ref(AWS_REGION), ".amazonaws.com"]),
            CustomOriginConfig=CustomOriginConfig(
                HTTPPort=80,
                HTTPSPort=443,
                OriginProtocolPolicy='https-only',
            ),
            OriginCustomHeaders=[OriginCustomHeader(
                HeaderName='x-api-key',
                HeaderValue=api_key_secret,
            ), OriginCustomHeader(
                HeaderName='x-video-table',
                HeaderValue=Ref(video_table),
            )],
        )],
        PriceClass='PriceClass_100',
        ViewerCertificate=ViewerCertificate(
            AcmCertificateArn=Ref(cloudfront_certificate),
            SslSupportMethod='sni-only',
            MinimumProtocolVersion='TLSv1.1_2016',  # We might need to raise this
        ),
    ),
))

template.add_resource(RecordSetGroup(
    "DnsRecords",
    HostedZoneId=ImportValue(Join('-', [Ref(dns_stack), 'HostedZoneId'])),
    RecordSets=[RecordSet(
        Name=Ref(domain_name),
        Type='A',
        AliasTarget=AliasTarget(
            HostedZoneId='Z2FDTNDATAQYW2',
            DNSName=GetAtt(api_cdn, 'DomainName'),
        ),
    ), RecordSet(
        Name=Ref(domain_name),
        Type='AAAA',
        AliasTarget=AliasTarget(
            HostedZoneId='Z2FDTNDATAQYW2',
            DNSName=GetAtt(api_cdn, 'DomainName'),
        ),
    )],
    Comment=Join('', ['Record for CloudFront in ', Ref(AWS_STACK_NAME)]),
))

f = open("output/spunt_api.json", "w")
f.write(template.to_json())
