from flask import Flask, request
from flask_restful import Resource, Api, reqparse
from flask_cors import CORS
import uuid
import mysql.connector
import os
import subprocess
from twilio.rest import Client
import random
import jwt
import datetime
import logging
from decouple import config
import re

app = Flask(__name__)
CORS(app)
api = Api(app)

APP_NAME = config('APP_NAME')
JWT_SECRET = config('JWT_SECRET')
BASE_URL = config('BASE_URL')

# Set up a logger with a more readable format
logger = logging.getLogger()
if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)
logging.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s',level=logging.INFO)

#Todo: Enable proper logging
#Todo: Escape single quotes
class Register(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('phone', type = str, required = True, help = 'No phone was provided', location = 'json')
        super(Register, self).__init__()

    def post(self):
        self.reqparse.parse_args()
        json_data = request.get_json()
        
        
        if json_data["phone"] is None:
            return {
                "error": "Missing phone number"
            }
        json_data["phone"] = cleanData(json_data["phone"])

        # Validate the phone number
        is_valid_phone = isPhoneNumberValid(json_data["phone"])

        if is_valid_phone is None:
            return {
                "error": "Phone number is not valid"
            }
       
        # Check if a verified user exists with the phone number.
        verified_phone_exists = checkPhoneNumberExistsAndVerified(json_data["phone"])
        if verified_phone_exists:
            return {"error": "A user exists with this phone number. Please use a different phone number"}
        
        # Create a verification code and save it into the phone_auth table.
        auth_code = createAuthCode("PHONE", json_data["phone"])

        # Send phone verification message with auth code
        sendAuthCodeSMS(auth_code, json_data["phone"])
       
        return {"data": {
            "phone": json_data["phone"],
            "status": "Pending Verification"
        }}, 201
api.add_resource(Register, '/register-phone')

class Verify(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('phone', type = str, required = True, help = 'No phone was provided', location = 'json')
        self.reqparse.add_argument('auth_code', type = str, required = True, help = 'No verification code was provided', location = 'json')
        super(Verify, self).__init__()

    def post(self):
        self.reqparse.parse_args()
        json_data = request.get_json()

        if json_data["phone"] is None:
            return {
                "error": "Missing phone number. Please login"
            }
        json_data["phone"] = cleanData(json_data["phone"])
        response = {
            "phone": json_data["phone"]
        }
        
        # Verify if the user entered the correct code.
        phone = verifyPhone(json_data["phone"], json_data["auth_code"])

        if phone:
            response["status"] = "Verification Successful"
            user_id = phone[1]
            if user_id: # If user id exists it means the user is already registered and trying to login
                response["user_id"] =  user_id
            else:
                # Generate a new user_id
                response["user_id"] =  str(uuid.uuid4())
           
            # Set the is_verified flag and user_id
            updatePhoneVerifyFieldAndUserID(json_data["phone"], response["user_id"])

            # Generate a access token for the user
            access_token = generateJwtToken(response).decode("utf-8")
            response["access_token"] = str(access_token)
        else:
            return {
                "phone": json_data["phone"],
                "auth_code": json_data["auth_code"],
                "error": "The code entered is invalid. Please try again"
            }

        return {"data": response}, 200

api.add_resource(Verify, '/verify-phone')

class Profile(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('token', type = str, required = True, help = 'No access token was provided', location = 'json')
        self.reqparse.add_argument('first_name', type = str, required = True, help = 'No firstname  was provided', location = 'json')
        self.reqparse.add_argument('last_name', type = str, required = True, help = 'No lastname was provided', location = 'json')
        self.reqparse.add_argument('email', type = str, required = True, help = 'No email was provided', location = 'json')
        self.reqparse.add_argument('profession', type = str, required = True, help = 'No profession was provided', location = 'json')
        self.reqparse.add_argument('current_employer', type = str, required = True, help = 'No current employer was provided', location = 'json')
        self.reqparse.add_argument('description', type = str, required = True, help = 'No description was provided', location = 'json')
        self.reqparse.add_argument('top_skills', type = str, required = True, help = 'No top skills were provided', location = 'json')
        super(Profile, self).__init__()

    def post(self):
        self.reqparse.parse_args()
        json_data = request.get_json()

        jwt_payload = decodeJwttoken(json_data["token"])

        if "error" in jwt_payload:
            return jwt_payload

        user = getUser(jwt_payload["sub"])
        if user is None:
            return {"error": "Token provided is invalid. Please login"}
        
        # Only proceed with user creation if the phone number is verified
        verified_phone_exists = checkPhoneNumberExistsAndVerified(jwt_payload["phone"])
        
        if not verified_phone_exists:
            return {"error": "This phone number needs to be verified before creating the account"}

        if not json_data["first_name"]:
            return {"error": "First name cannot be empty"}
        
        if not json_data["last_name"]:
            return {"error": "Last name cannot be empty"}
        
        if not json_data["email"]:
            return {"error": "Email cannot be empty"}
        
        if not json_data["profession"]:
            return {"error": "Profession cannot be empty"}
        
        if not json_data["current_employer"]:
            return {"error": "Current employer cannot be empty"}

        # Save the incoming information.
        json_data["user_id"] = jwt_payload["sub"]
        json_data["first_name"] = cleanData(json_data["first_name"]).replace(" ", "-").lower()
        json_data["last_name"] = cleanData(json_data["last_name"]).replace(" ", "-").lower()
        json_data["email"] = json_data["email"]
        json_data["profession"] = cleanData(json_data["profession"])
        json_data["current_employer"] = cleanData(json_data["current_employer"])
        
        # Check if user exists
        user_info = getUserProfile(json_data["user_id"])
        if user_info:
            updateUserProfile(json_data)
        else:
            createUserProfile(json_data)

        # Save top skills
        top_skills = getUserTopSkills(json_data["user_id"])
        if top_skills is None:
            addUserTopSkills(json_data["user_id"], json_data["top_skills"])
        else:
            removeUserTopSkills(json_data["user_id"])
            addUserTopSkills(json_data["user_id"], json_data["top_skills"])

        # Check if the user already has a directory created.
        directory = getUserDirectory(json_data["user_id"])
        if directory is None:
            directory = generateUserDirectoryID(json_data["user_id"], json_data["first_name"], json_data["last_name"])

        # Start building profile.
        result = loadFullProfile(json_data["user_id"])
        if "error" in result:
            return result
        
        user_profile = result["data"]

        # Get all blog posts for user
        blog_posts = getAllBlogPostsForUser(json_data["user_id"])
        if blog_posts:
            startBuildingBlogPosts(blog_posts, user_profile)
        else:
            # Start the build process. # Todo: Track build stages
            startBuildingProfilePage(user_profile)

        # Notify that the build is completed.
        url = BASE_URL + "/" + directory
        sendBuildCompletedSMS(jwt_payload["phone"], "Profile", url)

        return {"data": json_data}, 200
api.add_resource(Profile, '/create-profile')

class Login(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('phone', type = str, required = True, help = 'No phone was provided', location = 'json')
        super(Login, self).__init__()

    def put(self):
        self.reqparse.parse_args()
        json_data = request.get_json()
        
        if json_data["phone"] is None:
            return {
                "error": "Missing phone number"
            }
        json_data["phone"] = cleanData(json_data["phone"])

        # Only proceed with user login if the phone number is verified
        verified_phone_exists = checkPhoneNumberExistsAndVerified(json_data["phone"])
        
        if not verified_phone_exists:
            return {"error": "This phone number needs to be registered and verified before login"}
        
        # Create a verification code and save it into the phone_auth table.
        auth_code = createAuthCode("PHONE", json_data["phone"])

        # Send phone verification message with auth code
        sendAuthCodeSMS(auth_code, json_data["phone"])

        return {"data": json_data, "message": "Verification Code Sent"}
api.add_resource(Login, '/login')

class CreateBlogPost(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('token', type = str, required = True, help = 'No access token was provided', location = 'json')
        self.reqparse.add_argument('title', type = str, required = True, help = 'No blog post title was provided', location = 'json')
        self.reqparse.add_argument('description', type = str, required = True, help = 'No blog post description was provided', location = 'json')
        super(CreateBlogPost, self).__init__()

    def post(self):
        self.reqparse.parse_args()
        json_data = request.get_json()

        jwt_payload = decodeJwttoken(json_data["token"])

        if "error" in jwt_payload:
            return jwt_payload

        user_id = jwt_payload["sub"]
        
        if json_data['title'] is None:
            return {
                "error": "A title is required to create a blog post"
            }
        
        if json_data['description'] is None:
            return {
                "error": "A description is required to create a blog post content"
            }
        
        user_profile_result = loadFullProfile(user_id)
        if "error" in user_profile_result:
            return user_profile_result
       
        # Save the blog post
        result = saveBlogPost(user_id, cleanData(json_data['title']), json_data['description'])
        if not result:
            return {
                "error": "Error creating your blog post"
            }

        # Get all blog posts for user
        blog_posts = getAllBlogPostsForUser(user_id)
        if blog_posts is None:
            return {
                "error": "Error fetching your blog posts"
            }

        # Start building the blog posts. # Todo: Track build stages and errors
        # Todo: This rebuilds all the blog posts and profile.
        # Should track the changed blog in /var/www/about-me.website/<user_directory> and move only the changed files
        startBuildingBlogPosts(blog_posts, user_profile_result['data'])

        # Get the current blog post
        current_blog_post = getMostRecentBlogPostForUser(user_id)
        if current_blog_post is None:
            return {
                "error": "Created blog post but could not fetch the url"
            }
        
        # Build the blog post url
        blog_post_name = current_blog_post["title"].replace(" ", "-").lower() + "-" + str(current_blog_post["post_id"])
        url = BASE_URL + "/" + user_profile_result['data']['directory_id'] + "/blog/" + blog_post_name

        # Notify that the build is completed
        sendBuildCompletedSMS(jwt_payload["phone"], "blog post", url)

        return {"data": {
            "status" : "Build Started"
        }}, 200
api.add_resource(CreateBlogPost, '/create-blog-post')

class Directory(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('token', type = str, required = True, help = 'No access token was provided', location = 'json')
        self.reqparse.add_argument('first_name', type = str, required = True, help = 'No first name was provided', location = 'json')
        self.reqparse.add_argument('last_name', type = str, required = True, help = 'No last name was provided', location = 'json')
        super(Directory, self).__init__()

    def get(self):
        self.reqparse.parse_args()
        json_data = request.get_json()

        # Validate the JWT token.
        jwt_payload = decodeJwttoken(json_data["token"])
        if "error" in jwt_payload:
            return jwt_payload
        
        user_id = jwt_payload["sub"]
        directory_id = getUserDirectory(user_id)
    
        return {"data": {
            "directory_id": directory_id
        }}, 200
api.add_resource(Directory, '/get-user-directory')

# Helper methods
def saveBlogPost(user_id, title, description):
    # Save the blog post to the user blog post table
    # Todo: Add a try catch block to return error if one occurs
    try:
        db = mysql.connector.connect(
            host=config('DB_HOST'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            database=config('DB_NAME')
        )

        cursor = db.cursor()
        sql = "INSERT INTO `user_blog_post` (user_id, title, description) VALUES \
            (%s, %s, %s)"

        val = (user_id, title, description)

        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        db.close()
        return True
    except mysql.connector.Error as err:
        print("Something went wrong: {}".format(err))
        return False
    
def getMostRecentBlogPostForUser(user_id):
    try:
        db = mysql.connector.connect(
            host=config('DB_HOST'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            database=config('DB_NAME')
        )
        
        cursor = db.cursor()
        sql = "SELECT * FROM `user_blog_post` WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
        val = (user_id, )
        cursor.execute(sql, val)

        result = cursor.fetchall()
        if len(result) == 0:
            return None
        
        record = result[0]
        return {
            "post_id": record[0],
            "user_id": record[1],
            "title": record[2],
            "created_at": str(record[3]),
            "description": record[4]
        }
    except mysql.connector.Error as err:
        print("Something went wrong: {}".format(err))
        return None

def getAllBlogPostsForUser(user_id):
    try:
        db = mysql.connector.connect(
            host=config('DB_HOST'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            database=config('DB_NAME')
        )
        
        cursor = db.cursor()
        sql = "SELECT * FROM `user_blog_post` WHERE user_id = %s ORDER BY created_at DESC LIMIT 10"
        val = (user_id, )
        cursor.execute(sql, val)

        result = cursor.fetchall()
        if len(result) == 0:
            return None
        
        blog_posts = []
        for post in result:
            blog_post = {}
            blog_post["post_id"] = post[0]
            blog_post["user_id"] = post[1]
            blog_post["title"] = post[2]
            blog_post["created_at"] = str(post[3])
            blog_post["description"] = post[4]
            blog_posts.append(blog_post)

        return blog_posts
    except mysql.connector.Error as err:
        print("Something went wrong: {}".format(err))
        return None

def getBlogPost(post_id, user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT * FROM `user_blog_post` WHERE post_id = %s user_id = %s LIMIT 1"
    val = (post_id, user_id)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    
    record = result[0]
    return {
        "post_id": record[0],
        "user_id": record[1],
        "title": record[2],
        "created_at": str(record[3]),
        "descritpion": record[4]
    }

def loadFullProfile(user_id):
    # Check if profile is created
    user_profile = getUserProfile(user_id)
    if user_profile is None:
        return {
            "error": "You must create a profile before I can build your profile page"
        }
    
    # Check if the user directory is created
    directory_id = getUserDirectory(user_profile["user_id"])
    if directory_id is None:
        return {
            "error": "No directory was generated"
        }
    user_profile["directory_id"] = directory_id

    # Check if the user has top skills
    top_skills = getUserTopSkills(user_profile["user_id"])
    if top_skills is None:
        return {
            "error": "Missing top skills"
        }
    
    user_profile["top_skills"] = top_skills
    return {
        "data": user_profile
    }

def getUserDirectory(user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT directory_id FROM user_directory WHERE user_id = %s LIMIT 1"
    val = (user_id,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    return result[0][0]

def generateUserDirectoryID(user_id, first_name, last_name):
    directory_id = first_name + "-" + last_name
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT count(directory_id) as total_count FROM user_directory WHERE directory_id = %s LIMIT 1"
    val = (directory_id,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        saveUserDirectory(user_id, directory_id)
    else:
        total_count = result[0][0]
        if total_count > 0:
            directory_id = directory_id + "-" + str(total_count)
        saveUserDirectory(user_id, directory_id)
    return directory_id

def saveUserDirectory(user_id, directory_id):
    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "INSERT INTO `user_directory` (directory_id, user_id) VALUES \
        (%s, %s)"

    val = (directory_id, user_id)

    cursor.execute(sql, val)
    db.commit()

# Build Section Helpers
# Runs a shell command. Throws an exception if fails.
def run_command(command):
    command_list = command.split(" ")
    try:
        logger.info("Running shell command: \"{0}\"".format(command))
        result = subprocess.run(command_list, stdout=subprocess.PIPE)
        logger.info("Command output:\n---\n{0}\n---".format(result.stdout.decode('UTF-8')))
    except Exception as e:
        logger.error("Exception: {0}".format(e))
        raise e
    return True

def build_blog_post_file(blog_post, local_source_dir, user_profile):
    # Todo: Add relavant meta tags in description
    # Todo: Escape single quote
    current_datetime = datetime.datetime.now()
    iso_formated_dt = current_datetime.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
    author = user_profile["first_name"] + " " + user_profile["last_name"]
    image_path = "images/blog/default-blog-post-image.jpg"
    blog_post_content = '---\ntitle: "{0}"\ndate: "{1}"\nimage: "{2}"\ndescription: "This is meta description"\nauthor: "{3}"\ntype: "post"\n---\n{4}'.format(blog_post["title"],
    iso_formated_dt, image_path, author, blog_post["description"])

    blog_post_name = blog_post["title"].replace(" ", "-")
    blog_post_file_path = local_source_dir + "/content/blog/" + blog_post_name + "-" +str(blog_post["post_id"]) + ".md"
    
    if os.path.exists(blog_post_file_path):
        os.remove(blog_post_file_path)
        logger.info('Removing old blog post file')
    file = open(blog_post_file_path, 'w')
    file.write(blog_post_content)
    file.close()
    run_command("cat {0}".format(blog_post_file_path))
    logger.info('Done generating blog post file')
        

def build_config(user_profile, user_directory, local_source_dir):
    config_data = 'baseURL = "https://about-me.website/{0}"\n\
    languageCode = "en-us"\n\
    title = "{1}\'s Website"\n\
    theme = "portfolio-theme"\n\
    summaryLength = "10"\n\
    \n\
    # Plugins\n\
    [params.plugins]\n\
    \n\
    # CSS Plugins\n\
    [[params.plugins.css]]\n\
    URL = "plugins/bootstrap/bootstrap.min.css"\n\
    [[params.plugins.css]]\n\
    URL = "plugins/slick/slick.css"\n\
    [[params.plugins.css]]\n\
    URL = "plugins/themify-icons/themify-icons.css"\n\
    \n\
    # JS Plugins\n\
    [[params.plugins.js]]\n\
    URL = "plugins/jQuery/jquery.min.js"\n\
    [[params.plugins.js]]\n\
    URL = "plugins/bootstrap/bootstrap.min.js"\n\
    [[params.plugins.js]]\n\
    URL = "plugins/slick/slick.min.js"\n\
    [[params.plugins.js]]\n\
    URL = "plugins/shuffle/shuffle.min.js"\n\
    \n\
    # navigation\n\
    [menu]\n\
    \n\
    [[menu.main]]\n\
    name = "Blog"\n\
    URL = "blog"\n\
    weight = 2\n\
    \n\
    [params]\n\
    logo = "images/logo.svg"\n\
    home = "Home"\n\
    # Meta data\n\
    description = "This is meta description"\n\
    author = "Themefisher"\n\
    # Google Analitycs\n\
    googleAnalitycsID = "Your ID"\n\
    \n\
    # Preloader\n\
    [params.preloader]\n\
    enable = true\n\
    \n\
    [params.contact]\n\
    enable = false\n\
    formAction = "#"\n\
    \n\
    [params.footer]\n\
    email = "{2}"\n\
    phone = "{3}"\n\
    address = "{4}"'.format(user_directory, user_profile["first_name"].title(), user_profile["email"], "N/A", "N/A")

    config_file_path = local_source_dir +"/config.toml"
    if os.path.exists(config_file_path):
        os.remove(config_file_path)
        logger.info('Removing old config file')
    file = open(config_file_path, 'w')
    file.write(config_data)
    file.close()
    run_command("cat {0}".format(config_file_path))
    logger.info('Done generating config file')
    
def build_user_fields_yaml(user_profile, user_directory):
    author_image = '"/images/default-profile-pic.png"'
    if user_profile["profile_pic"]:
        author_image = '"' + user_directory + '"' + '"/images/profile/{0}"'.format(user_profile["profile_pic"])
    USER_FIELDS = {
        "title" : '"About Me"',
        "date_created" : '2019-05-12T12:14:34+06:00',
        "description" : '"Building things step by step"',
        "author" : '"{0} {1}"'.format(user_profile["first_name"].title(), user_profile["last_name"].title()),
        "author_image" : author_image,
        "author_signature" : '"images/about/signature.png"',
        "page_content" : '"{0}"'.format(user_profile["description"]),
        "profession" : '"{0}"'.format(user_profile["profession"]),
        "current_employer": '"{0}"'.format(user_profile["current_employer"])
    }
    
    # Read these fields from the DB
    logger.info('Building user fields YAML')
    REFERENCE_TEMPLATE_YAML = "info:\n  title: {0}\n  date: {1}\n  description: {2}\n  author: {3}\n  authorImage: {4}\n  authorSignature: {5}\n  content: {6}\n  profession: {7}\n  currentEmployeer: {8}"\
    .format(USER_FIELDS["title"], USER_FIELDS["date_created"], USER_FIELDS["description"], USER_FIELDS["author"], \
    USER_FIELDS["author_image"], USER_FIELDS["author_signature"], USER_FIELDS["page_content"], USER_FIELDS["profession"], USER_FIELDS["current_employer"])
    logger.info('Done building user fields YAML')
    
    return REFERENCE_TEMPLATE_YAML
    
def build_skills_yaml(user_profile):
    skills = user_profile["top_skills"]
    if len(skills) == 0 :
        return
    
    # Read these fields from the DB
    logger.info('Building user skills YAML')
    REFERENCE_TEMPLATE_SKILLS_YAML = "skill:\n\
      enable: true\n\
      skillbar:\n\
        - title: \"{0}\"\n\
          progress: \"80%\"\n\
          color: \"#fdb157\"\n\
        - title: \"{1}\"\n\
          progress: \"80%\"\n\
          color: \"#9473e6\"\n\
        - title: \"{2}\"\n\
          progress: \"80%\"\n\
          color: \"#bdecf6\"".format(user_profile["top_skills"][0], user_profile["top_skills"][1], user_profile["top_skills"][2])
    
    logger.info('Done building skill fields YAML')

    return REFERENCE_TEMPLATE_SKILLS_YAML


# Copies template from ~/hugo-templates/default-templates to /tmp/hugo_source
def copy_template_to_temp_dir(local_template_home, local_source_dir):
    if os.path.isdir(local_source_dir):
        run_command("rm -rd {0}".format(local_source_dir))
    run_command("mkdir {0}".format(local_source_dir))
    logger.info('Starting copying template folder to {0}'.format(local_source_dir))
    run_command("cp -a {0} {1}".format(local_template_home+"/.", local_source_dir+"/"))
    run_command("ls -l {0}".format(local_source_dir))
    logger.info('Done copying template folder to {0}'.format(local_source_dir))

# Build about-me template
def generate_about_me_page(local_source_dir, reference_template):
    logger.info('Generating about me page')

    # Write the string REFERENCE_TEMPLATE to file.
    about_page_dir = local_source_dir + "/content/about/"
    if not os.path.isdir(about_page_dir):
        run_command("mkdir {0}".format(about_page_dir))
    about_page_file_path = about_page_dir + "_index.md"
    
    if os.path.exists(about_page_file_path):
        os.remove(about_page_file_path)
        logger.info('Removing old files')
    #run_command('touch {0}'.format(about_page_file_path))
    file = open(about_page_file_path, 'w')
    file.write(reference_template)
    file.close()
    run_command("cat {0}".format(about_page_file_path))
    logger.info('Done generating about me page')

def generate_about_me_section_yaml(local_source_dir, reference_template_yaml):
    logger.info('Generating about info section yaml')

    # Write the string REFERENCE_TEMPLATE to file.
    about_info_data_dir = local_source_dir + "/data/"
    if not os.path.isdir(about_info_data_dir):
        run_command("mkdir {0}".format(about_info_data_dir))
    about_info_file_path = about_info_data_dir + "aboutinfo.yml"
    
    if os.path.exists(about_info_file_path):
        os.remove(about_info_file_path)
        logger.info('Removing old files')
    #run_command('touch {0}'.format(about_info_file_path))
    file = open(about_info_file_path, 'w')
    file.write(reference_template_yaml)
    file.close()
    run_command("cat {0}".format(about_info_file_path))
    logger.info('Done generating about info section yaml')
    
def generate_skills_section_yaml(user_profile, local_source_dir, reference_template_skills_yaml):
    if len(user_profile["top_skills"]) == 0:
        logger.info('No top skills found. So skipping this step')
        return
    logger.info('Generating about info section yaml')

    # Write the string REFERENCE_TEMPLATE to file.
    skills_file_path = local_source_dir + "/data/skillsinfo.yml"
    if os.path.exists(skills_file_path):
        os.remove(skills_file_path)
        logger.info('Removing old files')
    
    run_command("touch {0}".format(skills_file_path))
    file = open(skills_file_path, 'w')
    file.write(reference_template_skills_yaml)
    file.close()
    run_command("cat {0}".format(skills_file_path))
    logger.info('Done generating skill info section yaml')

# Builds a hugo website
def build_hugo(source_dir, destination_dir, debug=False):
    if os.path.isdir(destination_dir):
        run_command("rm -rd {0}".format(destination_dir))
    run_command("mkdir {0}".format(destination_dir))
    logger.info("Building Hugo site")
    run_command("/usr/local/bin/hugo -s {0} -d {1}".format(source_dir,destination_dir))
    run_command("ls -l {0}".format(destination_dir))
    logger.info('Done building hugo public assets')

def copy_build_to_destination(build_dir, destination_dir):
    logger.info('Starting copying build folder to destination')
    if os.path.isdir(destination_dir):
        run_command("rm -rd {0}".format(destination_dir))
    run_command("mkdir {0}".format(destination_dir))
    run_command("cp -a {0} {1}".format(build_dir+"/.", destination_dir+"/"))
    run_command("ls -l {0}".format(destination_dir))
    logger.info('Done copying build folder to destination')


def startBuildingProfilePage(user_profile):
    USER_DIRECTORY = user_profile["directory_id"]
    user_profile["phone"] = "N/A"
    LOCAL_SOURCE_DIR = "/tmp/"+ USER_DIRECTORY + "-hugo-source"
    LOCAL_BUILD_DIR = "/tmp/" + USER_DIRECTORY + "-hugo-build"
    LOCAL_TEMPLATE_HOME = config('LOCAL_TEMPLATE_HOME')
    
    # Build workflow.
    # 1). Copy template to lambda temp directory.
    copy_template_to_temp_dir(LOCAL_TEMPLATE_HOME, LOCAL_SOURCE_DIR)

    # 2). Build config file.
    build_config(user_profile, user_profile["directory_id"], LOCAL_SOURCE_DIR)

    # 3). Read from DB and build the user about me fields.
    REFERENCE_TEMPLATE_YAML = build_user_fields_yaml(user_profile, USER_DIRECTORY)
    REFERENCE_TEMPLATE_SKILLS_YAML = build_skills_yaml(user_profile)

    # 4). Using the user fields string generate the about me .md file in the LOCAL_SOURCE_DIR directory
    generate_about_me_section_yaml(LOCAL_SOURCE_DIR, REFERENCE_TEMPLATE_YAML)
    generate_skills_section_yaml(user_profile, LOCAL_SOURCE_DIR, REFERENCE_TEMPLATE_SKILLS_YAML)

    # 5). Build the files using hugo available at /var/task/hugo included with the deployment package
    build_hugo(LOCAL_SOURCE_DIR, LOCAL_BUILD_DIR)

    # 6). Copy build to destination /var/www/about-me.website/html
    DESTINATION_DIRECTORY = config('WWW_ROOT') + USER_DIRECTORY
    copy_build_to_destination(LOCAL_BUILD_DIR, DESTINATION_DIRECTORY)

def startBuildingBlogPosts(blog_posts, user_profile):
    user_profile["first_name"] = user_profile["first_name"].title()
    user_profile["last_name"] = user_profile["last_name"].title()
    USER_DIRECTORY = user_profile["directory_id"]
    LOCAL_SOURCE_DIR = "/tmp/"+ USER_DIRECTORY + "-hugo-source"
    LOCAL_BUILD_DIR = "/tmp/" + USER_DIRECTORY + "-hugo-build"
    LOCAL_TEMPLATE_HOME = config('LOCAL_TEMPLATE_HOME')
    
    # Build workflow.
    # 1). Copy template to lambda temp directory.
    copy_template_to_temp_dir(LOCAL_TEMPLATE_HOME, LOCAL_SOURCE_DIR)
    
    # 2). Build config file.
    build_config(user_profile, USER_DIRECTORY, LOCAL_SOURCE_DIR)

    # 3). Read from DB and build the user about me fields.
    REFERENCE_TEMPLATE_YAML = build_user_fields_yaml(user_profile, USER_DIRECTORY)
    REFERENCE_TEMPLATE_SKILLS_YAML = build_skills_yaml(user_profile)

    # 4). Using the user fields string generate the about me .md file in the LOCAL_SOURCE_DIR directory
    generate_about_me_section_yaml(LOCAL_SOURCE_DIR, REFERENCE_TEMPLATE_YAML)
    generate_skills_section_yaml(user_profile, LOCAL_SOURCE_DIR, REFERENCE_TEMPLATE_SKILLS_YAML)
   
    # 4b). Build a new blog post file for each blog post.
    for blog_post in blog_posts:
        build_blog_post_file(blog_post, LOCAL_SOURCE_DIR, user_profile)

    # 5). Build the files using hugo available at /var/task/hugo included with the deployment package
    build_hugo(LOCAL_SOURCE_DIR, LOCAL_BUILD_DIR)

    # 6). Copy build to destination /var/www/about-me.website/html
    DESTINATION_DIRECTORY = config('WWW_ROOT') + USER_DIRECTORY
    copy_build_to_destination(LOCAL_BUILD_DIR, DESTINATION_DIRECTORY)

# Todo: Add clean to all fields
def cleanData(data):
    data = data.replace(".", "")
    return data

def generateJwtToken(payload):
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=365, seconds=0),
            'iat': datetime.datetime.utcnow(),
            'sub': payload["user_id"],
            'phone': payload["phone"]
        }
        return jwt.encode(
            payload,
            JWT_SECRET,
            algorithm='HS256'
        )
    except Exception as e:
        return e

def decodeJwttoken(jwtToken):
    try:
        payload = jwt.decode(jwtToken, JWT_SECRET)
        return {
            "sub" : payload['sub'],
            "phone": payload['phone']
        }
    except jwt.ExpiredSignatureError:
        return {
            "error": "Signature expired. Please log in again."
        }
    except jwt.InvalidTokenError:
        return {
            "error": "Invalid token. Please log in again."
        }

def checkPhoneNumberExistsAndVerified(phone):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT phone FROM phone_auth WHERE phone = %s AND is_verified = true LIMIT 1"
    val = (phone,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return False
    return True

def addUserTopSkills(user_id, top_skills):
    if len(top_skills) > 0:
        for skill_name in top_skills:
            addTopSkill(user_id, cleanData(skill_name))

def addTopSkill(user_id, skill_name):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "INSERT INTO `user_top_skill` (user_id, skill_name) VALUES \
        (%s, %s)"

    val = (user_id, skill_name)

    cursor.execute(sql, val)
    db.commit()

def getUserTopSkills(user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT * FROM user_top_skill WHERE user_id = %s LIMIT 3"
    val = (user_id,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    
    skill_names = []
    for skill in result:
        skill_names.append(skill[2])

    return skill_names

def removeUserTopSkills(user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "DELETE FROM user_top_skill WHERE user_id = %s"
    val = (user_id,)
    cursor.execute(sql, val)
    db.commit()

def createUserProfile(userinfo):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "INSERT INTO `user` (user_id, first_name, last_name, email, current_employer, description, profession) VALUES \
        (%s, %s, %s, %s, %s, %s, %s)"

    val = (userinfo['user_id'], userinfo['first_name'],
    userinfo['last_name'], userinfo['email'], userinfo['current_employer'], userinfo['description'], userinfo['profession'])

    cursor.execute(sql, val)
    db.commit()


def getUserProfile(user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )
    
    cursor = db.cursor()
    sql = "SELECT * FROM user WHERE user_id = %s LIMIT 1"
    val = (user_id,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    user_record = result[0]
    output = {
        "user_id": user_record[0],
        "first_name": user_record[1],
        "last_name": user_record[2],
        "email": user_record[3],
        "current_employer": user_record[4],
        "description": user_record[5],
        "profession": user_record[6],
        "profile_pic": user_record[7]
    }

    return output

def updateUserProfile(userinfo):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()

    sql = "UPDATE `user` SET first_name = %s, last_name = %s, email = %s, current_employer = %s, description = %s, profession = %s \
        WHERE user_id = %s"

    val = (userinfo['first_name'], userinfo['last_name'], 
    userinfo['email'], userinfo['current_employer'], 
    userinfo['description'], userinfo['profession'], userinfo["user_id"])

    cursor.execute(sql, val)
    db.commit()

def isPhoneVerified(user_id):
    # Check if the user phone is already verified
    pass

def getUserFromPhone(phone):
    pass

# Todo: This phone_auth table could be just an auth table with different modes
def getUserIDFromPhone(phone):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "SELECT user_id FROM phone_auth WHERE phone = %s ORDER BY auth_time_stamp DESC LIMIT 1"
    val = (phone,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    return result[0]

def getUser(user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "SELECT user_id FROM phone_auth WHERE user_id = %s ORDER BY auth_time_stamp DESC LIMIT 1"
    val = (user_id,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    return result[0]

def verifyPhone(phone, auth_code):
    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()

    # Ignore the expiry for now (Todo: Check the expiration time with the current time)
    sql = "SELECT phone, user_id FROM phone_auth WHERE phone = %s AND auth_code = %s \
        ORDER BY auth_time_stamp DESC LIMIT 1"
    val = (phone, auth_code)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return None
    return result[0]

def updatePhoneVerifyFieldAndUserID(phone, user_id):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "UPDATE `phone_auth` SET is_verified = true, user_id = %s WHERE phone = %s"
    val = (user_id, phone)
    cursor.execute(sql, val)
    db.commit()
    return True

def verifyUser(user_id, auth_code, auth_method):
    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()

    # Ignore the expiry for now (Todo: Check the expiration time with the current time)
    sql = "SELECT user_id, auth_code FROM user_auth WHERE user_id = %s AND auth_code = %s AND auth_method = %s \
        ORDER BY auth_time_stamp DESC LIMIT 1"
    val = (user_id, auth_code, auth_method)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return False
    return True

def updateUserVerifyField(user_id, auth_method):
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "UPDATE `user` "
    if auth_method == "PHONE":
        sql = sql + " SET is_phone_verified = true "
    elif auth_method == "EMAIL":
        sql = sql + " SET is_email_verified = true "
    else:
        return False
    sql = sql + " WHERE user_id = %s"

    val = (user_id, )
    cursor.execute(sql, val)
    db.commit()
    return True

def createAuthCodeForUser(user_id, auth_method):
    # Generate a 4 digit random number
    auth_code = random.randint(1000, 9999)

    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()
    sql = "INSERT INTO `user_auth` (user_id, auth_code, auth_method) VALUES \
        (%s, %s, %s)"

    val = (user_id, auth_code, auth_method)

    cursor.execute(sql, val)
    db.commit()


    return auth_code

def phoneRecordExists(phone):
    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()

    # Ignore the expiry for now (Todo: Check the expiration time with the current time)
    sql = "SELECT phone FROM phone_auth WHERE phone = %s LIMIT 1"
    val = (phone,)
    cursor.execute(sql, val)

    result = cursor.fetchall()
    if len(result) == 0:
        return False
    return True

def createAuthCode(auth_method, value):
    # Todo: Add a limiter to ensure new codes are not sent within 10 min of creation
    # Todo: Add expiration as epoch, update timestamp when record is updated
    # Generate a 4 digit random number
    auth_code = random.randint(1000, 9999)

    # Save the number to the user_auth table
    db = mysql.connector.connect(
        host=config('DB_HOST'),
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        database=config('DB_NAME')
    )

    cursor = db.cursor()

    sql = ""
    if auth_method == "PHONE":
        phone_record_exists = phoneRecordExists(value)
        if phone_record_exists: # Ensures unique phone record
            sql = sql + "UPDATE `phone_auth` SET auth_code = %s WHERE phone = %s"
        else:
            sql = sql + "INSERT INTO `phone_auth` (auth_code, phone) VALUES (%s, %s)"
    else:
        sql = sql + "INSERT INTO `email_auth` (auth_code, email) VALUES (%s, %s)"

    val = (auth_code, value)

    cursor.execute(sql, val)
    db.commit()

    return auth_code

# Check if phone number is valid (supports US numbers xxx-yyy-zzzz, xxxyyyzzzz, +1 xxx-yyy-zzzz etc.)
def isPhoneNumberValid(phone):
    pattern = re.compile(r"^(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
    return pattern.match(phone)

# Send auth code to the phone. Uses TWILIO API to send the SMS
def sendAuthCodeSMS(auth_code, phone_number):
    account_sid = config('TWILIO_ACCOUNT_SID')
    auth_token = config('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)

    message_output = client.messages \
        .create(
            body="{0}:Your one time code is: {1}. Please say or enter the code in the {2} app to complete verification".format(APP_NAME, auth_code, APP_NAME),
            from_='+17865094977',
            to=phone_number
        )
    print(message_output)

# Send public url of the target to the phone. Uses TWILIO API to send the SMS
def sendBuildCompletedSMS(phone_number, target, url):
    account_sid = config('TWILIO_ACCOUNT_SID')
    auth_token = config('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)

    message_output = client.messages \
        .create(
            body="{0}:Your {1} page can be accessed using this link: {2}".format(APP_NAME, target, url),
            from_='+17865094977',
            to=phone_number
        )
    print(message_output)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)