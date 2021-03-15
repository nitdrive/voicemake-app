# Voicemake.io Client
# Version - 0.1.0

# Microsoft Azure AI Services used to develop this client app:
- Speech to Text - For converting the user speech to text
- LUIS (Language Understanding) - For understanding the main intent of the user's input, the text from previous step is used as input in this step
- Text to Speech - For generating the output response speech used for asking specific questions based on the main intent recognized
- Azure CDN - It will be used for hosting this client application and make it easily available to users from different geographic locations

# Use the client to create profile and blog posts with voice. The created profile and blog posts will be available at: 
# https://about-me.website/<user_directory>

# The following commands are available before login
# Each command has a set of questions that need to be answered to fulfill the intent.

# The commands need not be single word. They can be "Register my account", "Verify my phone", "Create my profile", "Create a post" etc.
- Register: Used to register a new user. The users are identified by their phone numbers, so the phone numbers are registered
- Verify: Used to verify a user phone number. This is done using one time verification codes sent to the user's phone which they need to confirm
- Login: Same input as register. The user says their phone number and a one time verification code is sent to the user's phone, the user then needs to say 'Verify' and confirm the phone.

Note: Each time a user verifies their phone, a new access token is generated. This access token needs to be passed with all the requests post authenication.

# The following commands are available after login

- Create Profile - Used to create the user's profile based on the questions answered. A sharable link will be sent to the registered phone which can be used to access the profile page
- Create Blog Post - Used to create a new blog post based on the questions answered. A sharable link will be sent to the registered phone which can be used to access the blog post page