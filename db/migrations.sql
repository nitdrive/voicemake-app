create database easydb;
use easydb;

CREATE TABLE phone_auth (phone VARCHAR(100) NOT NULL, auth_code INT(10) NOT NULL, auth_code_expiry INT NOT NULL DEFAULT 15, is_verified BOOLEAN NOT NULL DEFAULT false, user_id varchar(100), auth_time_stamp datetime NOT NULL DEFAULT now(), PRIMARY KEY(phone));

ALTER TABLE phone_auth ADD unique(user_id);
ALTER TABLE `phone_auth` ADD INDEX `phone_auth_user_id_index` (`user_id`);

CREATE TABLE email_auth (email VARCHAR(200) NOT NULL, auth_code INT(10) NOT NULL, is_verified BOOLEAN NOT NULL DEFAULT false, auth_code_expiry INT NOT NULL DEFAULT 15, user_id varchar(100), auth_time_stamp datetime NOT NULL DEFAULT now(), PRIMARY KEY(email));

CREATE TABLE user (
	user_id VARCHAR(100) NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL,
	email VARCHAR(200), 
	current_employer VARCHAR(200), 
	description VARCHAR(500),
	profession VARCHAR(100), 
	profile_pic VARCHAR(500),
	created_at datetime NOT NULL DEFAULT now(),
	primary key(user_id),
	foreign key(user_id) REFERENCES phone_auth(user_id) ON UPDATE CASCADE
);

create table user_top_skill (
	skill_id INT NOT NULL AUTO_INCREMENT,
	user_id VARCHAR(100) NOT NULL,
	skill_name VARCHAR(200) NOT NULL,
	primary key(skill_id),
	foreign key(user_id) REFERENCES user(user_id)
);

create table user_blog_post (
	post_id INT NOT NULL AUTO_INCREMENT,
	user_id VARCHAR(100) NOT NULL,
	title VARCHAR(300) NOT NULL,
	created_at datetime default now(),
	description TEXT NOT NULL,
	primary key(post_id),
	foreign key(user_id) REFERENCES user(user_id)
);

CREATE TABLE user_directory(
	directory_id VARCHAR(100) NOT NULL, 
	user_id VARCHAR(100) NOT NULL, 
	count INT UNSIGNED NOT NULL DEFAULT 1, 
	PRIMARY KEY(directory_id),
	foreign key(user_id) REFERENCES user(user_id)

);