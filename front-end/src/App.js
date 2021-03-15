import React, { Component } from 'react';
import { Container, InputGroup } from 'reactstrap';
import { getTokenOrRefresh } from './token_util';
import './custom.css'
import { CancellationReason, ResultReason } from 'microsoft-cognitiveservices-speech-sdk';
import axios from 'axios';
import events from 'events';
import { NONAME } from 'dns';

const speechsdk = require('microsoft-cognitiveservices-speech-sdk')
let intents = {
    "create_profile" : {
        "questions_count": 9,
        "execute_action": "CREATE:PROFILE",
        "api_endpoint": "https://api.about-me.website/create-profile",
        "next_intent": undefined,
        "questions": [
            {
                "key": "first_name",
                "question": "What is your first name?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "last_name",
                "question": "What is your last name?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "email",
                "question": "What is your email?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "profession",
                "question": "What is your profession?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "current_employer",
                "question":  "Who you is your current employer? You can say self-employed or un-employeed if applicable",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "top_skill_1",
                "question":  "What is your top skill?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "top_skill_2",
                "question":  "What is your second best skill?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "top_skill_3",
                "question":  "What is your third best skill?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "description",
                "question": "Tell me about yourself?",
                "answer": "",
                "multi_line": true
            }
        ]
    },
    "create_blog_post" : {
        "questions_count": 2,
        "execute_action": "CREATE:BLOG:POST",
        "api_endpoint": "https://api.about-me.website/create-blog-post",
        "next_intent": undefined,
        "questions": [
            {
                "key": "title",
                "question": "What is the title of the blog post?",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "description",
                "question": "What is the content of the blog post?",
                "answer": "",
                "multi_line": true
            }
        ]
    },
    "register" : {
        "execute_action": "REGISTER:PHONE",
        "api_endpoint": "https://api.about-me.website/register-phone",
        "questions_count": 1,
        "questions": [
            {
                "key": "phone",
                "question": "You can now register your phone number. What is your phone number?",
                "answer": "",
                "multi_line": false
            }
        ],
        "next_intent": "verify"
    },
    "verify": {
        "execute_action": "VERIFY:PHONE",
        "api_endpoint": "https://api.about-me.website/verify-phone",
        "questions_count": 2,
        "questions": [
            {
                "key": "auth_code",
                "question": "Please say the four digit code you received on your phone",
                "answer": "",
                "multi_line": false
            },
            {
                "key": "phone",
                "question": "What is your phone number?",
                "answer": "",
                "multi_line": false
            }
        ],
        "next_intent": undefined
    },
    "login": {
        "execute_action": "LOGIN:WITH:PHONE",
        "questions_count": 1,
        "api_endpoint": "https://api.about-me.website/login",
        "questions": [
            {
                "key": "phone",
                "question": "What is your phone number?",
                "answer": "",
                "multi_line": false
            }
        ],
        "next_intent": "verify"
    },
    "logout": {
        "execute_action": "LOGOUT"
    }
};

let responseQuestions = {
    "REGISTER:PHONE": {
        "response": {
            "value": "I sent a one time four digit verification code to your phone, once you receive it please click on the mic button on this page and say 'Verify' and then read the four digit code one digit at a time"
        }
    },
    "VERIFY:PHONE": {
        "response": {
            "value": "You are now logged in. The following voice commands are now available. 'Create Profile', 'Create Blog Post'"
        }
    },
    "LOGIN:WITH:PHONE": {
        "response": {
            "value": "I sent a one time four digit verification code to your phone, once you receive it please click on the mic button on this page and say 'Verify' and then read the four digit code one digit at a time"
        }
    },
    "CREATE:PROFILE": {
        "response": {
            "value": "I started building your profile page. You will be notified once the build is completed"
        }
    },
    "CREATE:BLOG:POST": {
        "response": {
            "value": "I started building your blog post page. You will be notified once the build is completed"
        }
    },
    "LOGOUT": {
        "response": {
            "value": "You are now logged out. You can login again by saying 'Login'"
        }
    }
};

class Job extends events.EventEmitter{}

export default class App extends Component {
    
    constructor(props) {
        super(props);


        this.state = {
            displayText: 'INITIALIZED: ready to test speech...',
            token: undefined
        }
        this.currentIntent = undefined;
        this.currentQuestionIndex = undefined;
        
        this.job = new Job();
        this.job.on('unsupported_browser', async () => {
            await this.createResponseSpeechOutput("This browser is not supported. Please use a latest browser or update your browser");
        });

        this.job.on('play_question', async () => {
            const questions = intents[this.currentIntent]["questions"];
            await this.createSpeechOutput(questions[this.currentQuestionIndex]["question"]);
        });

        this.job.on('question_played' , async () => {
            if(intents[this.currentIntent]["questions"][this.currentQuestionIndex]["multi_line"]) {
                await this.recordAnswerContinuous(this.currentIntent, this.currentQuestionIndex, 60000);
            } else {
                await this.recordAnswer(this.currentIntent, this.currentQuestionIndex);
            }
        });

        this.job.on('answer_recorded', async () => {
            this.currentQuestionIndex++;
            if(this.currentQuestionIndex !== undefined && this.currentQuestionIndex < intents[this.currentIntent]["questions_count"]) {
                if(this.currentIntent === "verify") {
                    const phone = await this.getObjectFromLocalStorage("phone");
                    console.log("Saved Phone:" + phone);
                    if(phone && Object.keys(phone).length === 0) {
                        this.job.emit("play_question");
                    } else {
                        intents[this.currentIntent]["questions"][this.currentQuestionIndex]["answer"] = phone;
                        this.currentQuestionIndex++;
                        this.job.emit('answer_recorded');
                    }
                } else {
                    this.job.emit("play_question");
                }
            } else {
                this.job.emit('start_execution', this.currentIntent);
                this.currentIntent = undefined;
                this.currentQuestionIndex = undefined;
                console.log(intents);
                
            }
        });

        this.job.on('start_execution', async (currentIntent) => {
            // Todo:Ask confirmation from the user.
            // confirmQuestions[intents[currentIntent]["build_action"]]["questions"][0];
            let result = {}
            // Pass the intent answers to an API
            if("create_profile" === currentIntent) {
                result = await this.createProfilePage();
            } else if("register" === currentIntent) {
                result = await this.registerPhone();
            } else if("login" === currentIntent) {
                result = await this.login();
            } else if("verify" === currentIntent) {
                result = await this.verify();
            } else if("create_blog_post" === currentIntent) {
                result = await this.createBlogPost();
            }

            // Todo: Make a error handler for different formats
            // 1). Http status code based - 400 or above
            // 2). Response payload contains "error" attribute
            if(result && "data" in result && "error" in result.data) {
                await this.createResponseSpeechOutput(result.data.error);
            } else if("error" in result) {
                await this.createResponseSpeechOutput(result.error);
            } else if(result.status >= 400 && "message" in result.data && result.data.message && Object.keys(result.data.message).length > 0) {
                for(let key in result.data.message) {
                    await this.createResponseSpeechOutput(result.data.message[key]);
                    break;
                }
            } else {
                // Tell the user about the status of the build
                await this.createResponseSpeechOutput(responseQuestions[intents[currentIntent]["execute_action"]]["response"]["value"]);
            }
        });
    }

    async createProfilePage() {
        const createProfileEndpoint = intents["create_profile"]["api_endpoint"];
        try{
            const questions = intents["create_profile"]["questions"];
            let payload = {};
            payload["top_skills"] = [];
            
            for(let pair of questions) {
                if(pair["key"].startsWith("top_skill")) {
                    payload["top_skills"].push(pair["answer"]);
                } else {
                    payload[pair["key"]] = pair["answer"];
                }
            }

            // If token does not exist. Return error message
            if(!await this.tokenExists()) {
                return {
                    "error" : "Missing access token. Please login and try again"
                }
            }
            let accessToken = await this.getObjectFromLocalStorage("access_token");

            payload["token"] = accessToken;

            const result = await axios.post(createProfileEndpoint, payload);
            console.log(result);
            
            return result;
        } catch(error) {
            return {"error": "Some required fields are missing" };
        }
    }

    async createBlogPost() {
        const createBlogPostEndpoint = intents["create_blog_post"]["api_endpoint"];
        try{
            const questions = intents["create_blog_post"]["questions"];
            let payload = {};
            
            for(let pair of questions) {
                payload[pair["key"]] = pair["answer"];
            }

            // If token does not exist. Return error message
            if(!await this.tokenExists()) {
                return {
                    "error" : "Missing access token. Please login and try again"
                }
            }
            let accessToken = await this.getObjectFromLocalStorage("access_token");

            payload["token"] = accessToken;

            const result = await axios.post(createBlogPostEndpoint, payload);
            console.log(result);
            
            return result;
        } catch(error) {
            return {"error": "Some required fields are missing" };
        }
    }

    async registerPhone() {
        const intentName = "register";
        const registerPhoneEndpoint = intents[intentName]["api_endpoint"];

        try{
            const questions = intents[intentName]["questions"];
            let payload = {};
            
            for(let pair of questions) {
                payload[pair["key"]] = pair["answer"];
            }
            
            // Save phone number to local storage.
            await this.saveObjectToLocalStorage({"key": "phone", "value": payload["phone"].replace(".", "")});

            const result = await axios.post(registerPhoneEndpoint, payload);
            console.log(result);
            
            return result;
        } catch(error) {
            console.log(error);
            return {};
        }

    }

    async login() {
        const intentName = "login";
        const loginEndpoint = intents[intentName]["api_endpoint"];

        try{
            const questions = intents[intentName]["questions"];
            let payload = {};
            
            for(let pair of questions) {
                payload[pair["key"]] = pair["answer"];
            }
           
            await this.saveObjectToLocalStorage({"key": "phone", "value": payload["phone"].replace(".", "")});
            const result = await axios.put(loginEndpoint, payload);
            console.log(result);
            
            return result;
        } catch(error) {
            console.log(error);
            return {};
        }
    }

    async verify() {
        const intentName = "verify";
        const loginEndpoint = intents[intentName]["api_endpoint"];

        try{
            const questions = intents[intentName]["questions"];
            let payload = {};
            
            // Fetch the phone number from local storage
            for(let pair of questions) {
                payload[pair["key"]] = pair["answer"];
            }

            if(payload["auth_code"] && Object.keys(payload["auth_code"]).length === 0) {
                return {"error": "Verfication code cannot be empty. Please try again"};
            }
            const result = await axios.post(loginEndpoint, payload);
            
            if("data" in result.data && "access_token" in result.data.data) {
                this.saveObjectToLocalStorage({"key": "phone", "value": result.data.data["phone"]});
                this.saveObjectToLocalStorage({"key": "access_token", "value": result.data.data["access_token"]});
                this.hideOrShow("pre-login", "none");
                this.hideOrShow("post-login", "block");
            }
            
            return result;
        } catch(error) {
            console.log(error);
            return {};
        }
    }

    async logout() {
        this.removeObjectFromLocalStorage("phone");
        this.removeObjectFromLocalStorage("access_token");
        this.hideOrShow("pre-login", "block");
        this.hideOrShow("post-login", "none");
        return {};
    }

    hideOrShow(className, displayState) {
        let elements = document.getElementsByClassName(className)

        for (let i = 0; i < elements.length; i++){
            elements[i].style.display = displayState;
        }
    }
    
    async componentDidMount() {
        // check for valid speech key/region
        const tokenRes = await getTokenOrRefresh();
        if (tokenRes.authToken === null) {
            this.setState({
                displayText: 'FATAL_ERROR: ' + tokenRes.error
            });
        }

        if(await this.tokenExists() && await this.phoneExists()) {
            console.log("Valid token and phone exists");
            this.hideOrShow("pre-login", "none");
            this.hideOrShow("post-login", "block");
        }
    }

    async componentWillUnmount() {
        this.job.removeAllListeners();
    }

    async saveObjectToLocalStorage(object) {
        if (typeof(Storage) !== "undefined") {
            localStorage.setItem(object["key"], object["value"]);
        } else {
            this.job.emit("unsupported_browser");
        }
    }

    async getObjectFromLocalStorage(key) {
        let object = undefined;
        if (typeof(Storage) !== "undefined") {
            object = localStorage.getItem(key);
        } else {
            this.job.emit("unsupported_browser");
        }
        return object;
    }

    async removeObjectFromLocalStorage(key) {
        if (typeof(Storage) !== "undefined") {
            localStorage.removeItem(key);
        } else {
            this.job.emit("unsupported_browser");
        }
    }

    async createSpeechOutput(speechText) {
        const tokenObj = await getTokenOrRefresh();
        const stream = speechsdk.AudioOutputStream.createPullStream();
        const audioConfig = speechsdk.AudioConfig.fromStreamOutput(stream);
        // const audioConfig = speechsdk.AudioConfig.fromAudioFileOutput(filename);
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);

        let synthesizer = new speechsdk.SpeechSynthesizer(speechConfig, audioConfig);
        synthesizer.speakTextAsync(speechText, async result => {
            if(result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted) {
                console.log("synthesis finished.");
                await this.play(result.privAudioData);
            } else {
                console.error("Speech synthesis canceled, " + result.errorDetails +
                "\nDid you update the subscription info?");
            }
            synthesizer.close();
            synthesizer = undefined;
        }, async err => {
            console.trace("err - " + err);
            synthesizer.close();
            synthesizer = undefined;
        });
    }

    async createResponseSpeechOutput(speechText) {
        const tokenObj = await getTokenOrRefresh();
        const stream = speechsdk.AudioOutputStream.createPullStream();
        const audioConfig = speechsdk.AudioConfig.fromStreamOutput(stream);
        // const audioConfig = speechsdk.AudioConfig.fromAudioFileOutput(filename);
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);

        let synthesizer = new speechsdk.SpeechSynthesizer(speechConfig, audioConfig);
        synthesizer.speakTextAsync(speechText, async result => {
            if(result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted) {
                console.log("synthesis finished.");
                await this.playConfirmMessage(result.privAudioData);
            } else {
                console.error("Speech synthesis canceled, " + result.errorDetails +
                "\nDid you update the subscription info?");
            }
            synthesizer.close();
            synthesizer = undefined;
        }, async err => {
            console.trace("err - " + err);
            synthesizer.close();
            synthesizer = undefined;
        });
    }

    async playConfirmMessage(data) {
        const context = new AudioContext();
        const buffer = await context.decodeAudioData(data);
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.onended = async (event) => {
            console.log("Stream Ended");
        }
        source.start();
        
    }

    async play(data) {
        const context = new AudioContext();
        const buffer = await context.decodeAudioData(data);
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.onended = async (event) => {
            console.log("Stream Ended");
            this.job.emit("question_played");
        }
        source.start();
        
    }

    async startListenFromMic() {
        //Stop any previous recordings in progress.
        this.job.emit("stop_continuous_recording");

        const tokenObj = await getTokenOrRefresh();
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);
        speechConfig.speechRecognitionLanguage = 'en-US';
        
        const audioConfig = speechsdk.AudioConfig.fromDefaultMicrophoneInput();
        const recognizer = new speechsdk.SpeechRecognizer(speechConfig, audioConfig);

        this.setState({
            displayText: 'speak into your microphone...'
        });

        recognizer.recognizeOnceAsync(async result => {
            let displayText;
            if (result.reason === ResultReason.RecognizedSpeech) {
                displayText = `RECOGNIZED: Text=${result.text}`
                await this.getMainIntent(result.text);
            } else {
                displayText = 'ERROR: Speech was cancelled or could not be recognized. Ensure your microphone is working properly.';
            }

            this.setState({
                displayText: displayText
            });
        });
    }

    async recordAnswerContinuous(currentIntent, currentQuestionIndex, timeout) {
        const tokenObj = await getTokenOrRefresh();
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);
        speechConfig.speechRecognitionLanguage = 'en-US';
        
        const audioConfig = speechsdk.AudioConfig.fromDefaultMicrophoneInput();
        const recognizer = new speechsdk.SpeechRecognizer(speechConfig, audioConfig);

        this.job.addListener("stop_continuous_recording", (e) => {
            recognizer.stopContinuousRecognitionAsync();
        });

        recognizer.sessionStarted = (sender, event) => {
            console.log("Session Started");
            document.getElementById("stop-recording-button").style.display = "block";
        }

        recognizer.recognized = (sender, event) => {
            let responseText;
            if(event.result.reason === ResultReason.RecognizedSpeech) {
                console.log("Speech Recognized");
                responseText = `RECOGNIZED Continuous: Text=${event.result.text}`
                console.log(responseText);
                let answer = intents[currentIntent]["questions"][currentQuestionIndex]["answer"];
                
                if(responseText) {
                    answer = answer + " " + event.result.text;
                    intents[currentIntent]["questions"][currentQuestionIndex]["answer"] = answer;
                }

                this.setState({
                    displayText: intents[currentIntent]["questions"][currentQuestionIndex]["answer"]
                });
            } else { // Show this on error.
                responseText = 'ERROR: Speech was cancelled or could not be recognized. Ensure your microphone is working properly.';
                console.log(responseText);
                console.log(event.result.reason);
            }
        }

        recognizer.canceled = (sender, event) => {
            let responseText;
            console.log("Speech Recognition Cancelled");
            if(event.reason == CancellationReason.Error) {
                responseText = 'ERROR: Speech was cancelled or could not be recognized. Ensure your microphone is working properly.';
                console.error(responseText);
            }
        }

        recognizer.sessionStopped = (sender, event) => {
            console.log("Session Stopped");
            document.getElementById("stop-recording-button").style.display = "none";
            this.job.emit('answer_recorded');
            this.job.removeListener("stop_continuous_recording");
        }

        recognizer.startContinuousRecognitionAsync();
        
        // End recording if timout is reached. Todo: Notify user that the recording has timedout and if needed reinitialize it.
        setTimeout(() => {
            recognizer.stopContinuousRecognitionAsync();
            document.getElementById("stop-recording-button").style.display = "none";
        }, timeout);
    }

    async recordAnswer(currentIntent, currentQuestionIndex) {
        //Stop any previous recordings in progress.
        this.job.emit("stop_continuous_recording");
        const tokenObj = await getTokenOrRefresh();
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);
        speechConfig.speechRecognitionLanguage = 'en-US';
        
        const audioConfig = speechsdk.AudioConfig.fromDefaultMicrophoneInput();
        const recognizer = new speechsdk.SpeechRecognizer(speechConfig, audioConfig);

        recognizer.recognizeOnceAsync(async result => {
            let responseText;
            if (result.reason === ResultReason.RecognizedSpeech) {
                responseText = `RECOGNIZED: Text=${result.text}`
                console.log(responseText);
                intents[currentIntent]["questions"][currentQuestionIndex]["answer"] = result.text;
                this.job.emit('answer_recorded');
            } else {
                responseText = 'ERROR: Speech was cancelled or could not be recognized. Ensure your microphone is working properly.';
                console.error(responseText);
                await this.createResponseSpeechOutput("Speech was cancelled or could not be recognized. Ensure your microphone is working properly and try again by clicking on the microphone button")
            }
        });
    }

    async getMainIntent(speechText) {
        let url = "<LUIS ENDPOINT URL>";
        try{
            const result = await axios.get(url + speechText);
            console.log(result);
            if(result.data.prediction["topIntent"] === "register") {
                this.currentIntent = "register"
            } else if(result.data.prediction["topIntent"] === "login") {
                this.currentIntent = "login"
            } else if(result.data.prediction["topIntent"] === "verify") {
                this.currentIntent = "verify"
            } else if(result.data.prediction["topIntent"] === "create_profile") {
                this.currentIntent = "create_profile";
                if(!await this.tokenExists()) {
                    await this.createResponseSpeechOutput("You must be a registered user and logged in before you can start creating your profile");
                    return {}
                }
            } else if (result.data.prediction["topIntent"] === "create_blog_post") {
                this.currentIntent = "create_blog_post";
                if(!await this.tokenExists()) {
                    await this.createResponseSpeechOutput("You must be a registered user and logged in before you can start creating your blog post");
                    return {}
                }
            }
            else if(result.data.prediction["topIntent"] === "logout") {
                this.currentIntent = "logout";
                await this.logout();
                await this.createResponseSpeechOutput(responseQuestions["LOGOUT"]["response"]["value"]);
                return {}
            }
            
            if(this.currentIntent !== undefined && this.currentIntent in intents) {
                this.currentQuestionIndex = 0;
                this.job.emit('play_question');
            }

            console.log(intents);
            return result;
        } catch(error) {
            console.log(error);
            return {};
        }
    }

    async tokenExists() {
        let accessToken =  await this.getObjectFromLocalStorage("access_token");
        if(!accessToken || accessToken && Object.keys(accessToken).length === 0) {
            return false;
        }
        return true;
    }

    async phoneExists() {
        let phone =  await this.getObjectFromLocalStorage("phone");
        if(!phone || phone && Object.keys(phone).length === 0) {
            return false;
        }
        return true;
    }

    async stopContinuousRecording() {
        this.job.emit("stop_continuous_recording");
    }

    async fileChange(event) {
        const audioFile = event.target.files[0];
        console.log(audioFile);
        const fileInfo = audioFile.name + ` size=${audioFile.size} bytes `;

        this.setState({
            displayText: fileInfo
        });

        const tokenObj = await getTokenOrRefresh();
        const speechConfig = speechsdk.SpeechConfig.fromAuthorizationToken(tokenObj.authToken, tokenObj.region);
        speechConfig.speechRecognitionLanguage = 'en-US';

        const audioConfig = speechsdk.AudioConfig.fromWavFileInput(audioFile);
        const recognizer = new speechsdk.SpeechRecognizer(speechConfig, audioConfig);

        recognizer.recognizeOnceAsync(result => {
            let displayText;
            if (result.reason === ResultReason.RecognizedSpeech) {
                displayText = `RECOGNIZED: Text=${result.text}`
            } else {
                displayText = 'ERROR: Speech was cancelled or could not be recognized. Ensure your microphone is working properly.';
            }

            this.setState({
                displayText: fileInfo + displayText
            });
        });
    }

    

    render() {
        return (
            <Container className="app-container">
                <div className="row">
                    <div className="col-12">
                        <div className="header">
                            <img src="/images/voicemake-logo-2.png" alt="voicemake.io - Build with voice" />
                            <h1>Home</h1>
                        </div>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12">
                        <div className="container">
                            <div className="center">
                                <i title="microphone-button" className="fas fa-microphone fa-lg mr-2 fa-10x" onClick={() => this.startListenFromMic()}></i>
                            </div>
                        </div>
                        <div className="mic-info-container">
                        <div className="center">
                            <h3>Click mic to speak</h3>
                        </div>
                        </div>
                    </div>
                    <div className="col-12">
                        <div className="center">
                            <button id="stop-recording-button" onClick={() => this.stopContinuousRecording()}>Stop Recording</button>
                        </div>
                        <br />
                    </div>
                </div>
                
                <div className="row">
                    <div className="col-12 output-display-info-title pre-login rounded">
                        <h5>Note: This app uses a passwordless authentication using one time verification codes sent to your phone</h5>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info-title pre-login rounded">
                        <h3>New Users: Please follow the steps below:</h3>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info pre-login">
                        <h3>Step 1</h3>
                        <code>Register your phone number by clicking on the microphone button and then say 'Register'</code>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info pre-login rounded">
                        <h3>Step 2</h3>
                        <code>Verify your phone number by clicking on the microphone button and then say 'Verify'</code>
                    </div>
                </div>

                <div className="row">
                    <div className="col-12 output-display-info-title pre-login rounded">
                        <h3>Existing Users: Please follow the steps below:</h3>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info pre-login rounded">
                        <h3>Step 1</h3>
                        <code>Login by clicking on the microphone button and then say 'Login'</code>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info pre-login rounded">
                        <h3>Step 2</h3>
                        <code>Verify your phone number again by clicking on the microphone button and then say 'Verify'</code>
                    </div>
                </div>

                <div className="row">
                    <div className="col-12 output-display-info-title post-login rounded">
                        <h3>The following commands are now available:</h3>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info post-login rounded">
                        <h3>Create Profile</h3>
                        <code>You can create your online profile page by clicking on the mic icon and saying 'Create Profile'</code>
                    </div>
                </div>
                <div className="row">
                    <div className="col-12 output-display-info post-login rounded">
                        <h3>Create Blog Post</h3>
                        <code>You can create a new blog post by clicking on the mic icon and saying 'Create Blog Post'</code>
                    </div>
                </div>
                {/* <div className="row">
                    <div className="col-12 output-display rounded">
                        <code>{this.state.displayText}</code>
                    </div>
                </div> */}
            </Container>
        );
    }
}