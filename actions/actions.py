# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk.executor import CollectingDispatcher
import pandas as pd
import json
import logging
import re
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
logging.basicConfig(level=logging.DEBUG, format= "%(funcName)s() - %(lineno)s - %(message)s")

ZomatoData = pd.read_csv('zomato.csv', encoding = "latin-1")
ZomatoData = ZomatoData.drop_duplicates().reset_index(drop=True)
WeOperate = ['New Delhi', 'Gurgaon', 'Noida', 'Faridabad', 'Allahabad', 'Bhubaneshwar',
 'Mangalore', 'Mumbai', 'Ranchi', 'Patna', 'Mysore', 'Aurangabad', 'Amritsar', 'Puducherry', 
 'Varanasi', 'Nagpur', 'Vadodara', 'Dehradun', 'Vizag', 'Agra', 'Ludhiana', 'Kanpur', 'Lucknow', 
 'Surat', 'Kochi', 'Indore', 'Ahmedabad', 'Coimbatore', 'Chennai', 'Guwahati', 'Jaipur', 'Hyderabad', 
 'Bangalore', 'Nashik', 'Pune', 'Kolkata', 'Bhopal', 'Goa', 'Chandigarh', 'Ghaziabad', 'Ooty', 
 'Gangtok', 'Shimla']

def RestaurantSearch(City,Cuisine, min_price, max_price, return_top=5):
	logging.info(f"Input City Name: {City}, Cuisine name: {Cuisine}, Price range: {min_price} to {max_price}")
	zomato_data = ZomatoData[(ZomatoData['Cuisines'].apply(lambda x: Cuisine.lower() in x.lower())) &
	 (ZomatoData['City'].apply(lambda x: City.lower() in x.lower())) &
	 (ZomatoData['Average Cost for two']>=min_price) &
	 (ZomatoData['Average Cost for two']<=max_price)
	 ]

	zomato_data = zomato_data[['Restaurant Name','Address','Average Cost for two','Aggregate rating']]
	zomato_data = zomato_data.sort_values(by='Aggregate rating', ascending=False)
	return zomato_data[:return_top]

def parse_price(raw_price):
	low_price= 0
	high_price = 100000
	temp = re.findall(r'\d+', raw_price)
	res = list(map(int, temp))
	logging.info(f"Price parse list: {res}")
	low_list = ['less', '<','within','low','']
	high_list = ['more','>', 'higher']
	# Logic to get the price
	if len(res)>1:
		low_price = res[0]
		high_price = res[-1]
	if len(res) == 1:
		b_flag = [ele for ele in high_list if(ele in raw_price)]
		if len(b_flag) > 0:    
			low_price = res[0]
		else:
			high_price = res[0]
	logging.info(f"Parsed low price: {low_price}, high price: {high_price}")
	return low_price, high_price

def format_message(df):
	resp = ""
	for _, restaurant in df.iterrows():
		r_temp = f" Restaurant Name: {restaurant['Restaurant Name']}\n Address: {restaurant['Address']}\n Average cost for two: {restaurant['Average Cost for two']} \n Rating is {restaurant['Aggregate rating']} \n {'-'*30} \n"
		resp += r_temp
	return resp

def prepare_email_html(df, cuisine, city):
	msg = f"<h3 style='color: blue;'>Here are top {cuisine} restaurants in {city}</h3>"
	for _, restaurant in df.iterrows():
		resp = f"""<p><b>Restaurant Name:</b> {restaurant['Restaurant Name']}<br> Address: 
					{restaurant['Address']}<br> Average cost for two: {restaurant['Average Cost for two']} <br> 
					Rating is {restaurant['Aggregate rating']} <br> {'-'*30} <br></p>"""
		msg += resp
	msg += f"""<p style='color: #a8000e'><b>From Team,</b> <br>
	 <b>Utkarsh and Faraz.</b></p>"""
	return msg

async def send_email(subject, mail_content, mail_html, receiver_address):
	sender_address = 'rasatest416@gmail.com'
	sender_pass = 'rasatest123'
	#Setup the MIME
	message = MIMEMultipart('alternative')
	message['From'] = sender_address
	message['To'] = receiver_address
	#The subject line
	message['Subject'] = subject
	#The body and the attachments for the mail
	#message.attach(MIMEText(mail_content, 'plain'))
	#Create SMTP session for sending the mail

	part1 = MIMEText(mail_content, 'plain')
	part2 = MIMEText(mail_html, 'html')

	# Attach parts into message container.
	# According to RFC 2046, the last part of a multipart message, in this case
	# the HTML message, is best and preferred.
	message.attach(part1)
	message.attach(part2)

	session = smtplib.SMTP('smtp.gmail.com', 587) #use gmail with port
	session.starttls() #enable security
	session.login(sender_address, sender_pass) #login with mail_id and password
	text = message.as_string()
	logging.info("Sending Email now.")
	session.sendmail(sender_address, receiver_address, text)
	session.quit()


class ActionSearchRestaurants(Action):
	def name(self):
		return 'action_search_restaurants'

	def run(self, dispatcher, tracker, domain):
		try:
			logging.info("In action_search_restaurants.")
			loc = tracker.get_slot('location')
			cuisine = tracker.get_slot('cuisine')
			price = tracker.get_slot('price')
			low_price, high_price = parse_price(price)
			logging.info(f"Parameters are: {loc}, {cuisine}, {price}")

			results = RestaurantSearch(loc, cuisine, low_price, high_price)
			logging.info(f"Length of Action search result: {results.shape[0]}")
			response=""
			if results.shape[0] == 0:
				response= "Oops! No result for given inputs."
			else:
				response = f"Here are the top 5 matches for your search: \n"
				response += format_message(results)
				
			dispatcher.utter_message(response)
		except Exception as e:
			logging.exception(f"Error in action_search_restaurants: {e}")
			dispatcher.utter_message("Opps! Something went wrong. Please rephrase your search and try again.")


class ActionCheckLocation(Action):
	def name(self):
		return 'action_check_location'

	def run(self, dispatcher, tracker, domain):
		try:
			logging.info("In action_check_location.")
			'''Checking for slot values.'''
			try:
				_ = tracker.get_slot('location')
				logging.info(f"Checking for Location slot. {_}")
			except Exception as e:
				logging.info('Location slot not set.')
			try:
				_ = tracker.get_slot('cuisine')
				logging.info(f"Checking for Cuisine slot. {_}")
			except Exception as e:
				logging.info("Cuisine slot not set.")
			try: 
				_ = tracker.get_slot('price')
				logging.info(f"Checking for Price slot. {_}")
			except Exception as e:
				logging.info("Price slot not set.")

			loc = tracker.get_slot('location')
			if loc.lower() in [x.lower() for x in WeOperate]:
				logging.info("deliver_to_location is true.")
				return [SlotSet('deliver_to_location',True)]
			else:
				logging.info("deliver_to_location is false.")
				return [SlotSet('deliver_to_location',False)]
		except Exception as e:
			logging.exception(f"Error in action_check_location: {e}")
			dispatcher.utter_message("Opps! Something went wrong. Please start again.")


class ActionSendEmail(Action):
	def name(self):
		return 'action_send_email'
	
	def run(self, dispatcher, tracker, domain):
		try:
			logging.info("In action_send_email.")
			#Get all entity values
			city = tracker.get_slot('location')
			cuisine = tracker.get_slot('cuisine')
			price = tracker.get_slot('price')
			receiver_address = tracker.get_slot('email_id')
			#receiver_address = "utkarsh.kumar4610@gmail.com"
			logging.info(f"Parameters are: {city}, {cuisine}, {price}, {receiver_address}")
			# Check email validatity
			pat = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b")
			is_email_valid = re.search(pat, receiver_address)
			if is_email_valid is None:
				logging.info("Email is invalid. Mail will not be sent.")
				dispatcher.utter_message("Provided email seems to be broken.")
				return

			mail_content=""
			top_n_rows=10
			#Call price range function
			price_low, price_high = parse_price(price)
			#Call search restaurants function
			searchData = RestaurantSearch(city, cuisine, price_low, price_high,top_n_rows)
			#Get search results in readable format
			if searchData.shape[0] == 0:
				'''
				This should never happen as this action is called immediately after action search restaurants
				Condition is just added as a fail safe to not send emails when nothing found
				'''
				dispatcher.utter_message("Email not sent as no restaurants were found for given search criteria")
			else:
				mail_content = "Below are the top "+ F"{top_n_rows} " + F"{cuisine}" + " restaurants in " + F"{city}:\n\n"
				mail_content += format_message(searchData)
				mail_html = prepare_email_html(searchData, cuisine, city)
				subject = f"Top {cuisine} restaurants in {city}."

				loop = asyncio.get_event_loop()
				task = loop.create_task(send_email(subject, mail_content, mail_html, receiver_address))

				dispatcher.utter_message("Email has been sent on given ID. It should reach shortly.")
		except Exception as e:
			logging.exception(f"Error in action_send_email: {e}")
			dispatcher.utter_message("Opps! Error in sending email. Please start again.")

class ActionSlotReset(Action):
	def name(self):
		return 'action_slot_reset'

	def run(self, dispatcher, tracker, domain):
		return [AllSlotsReset()]

