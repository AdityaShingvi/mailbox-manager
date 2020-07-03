#from __future___ import print_function
import pickle
import os.path
import re
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


SCOPES = ['https://mail.google.com/']
COMMON_DOMAINS = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
BATCH_SIZE = 50
NEXT_TOKEN = None

def _build_client():
	
	creds = None
	if os.path.exists('token.pickle'):
		with open('token.pickle', 'rb') as token:
			 creds = pickle.load(token)

	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
			creds = flow.run_local_server(port=0)
		
		with open('token.pickle', 'wb') as token:
			pickle.dump(creds, token)

	service = build('gmail', 'v1', credentials=creds)
	return service


def _list_messages(service, next_page_token):
	global NEXT_TOKEN
	if not next_page_token:
		result = service.users().messages().list(userId='me', maxResults=1000).execute()
	else:
		result = service.users().messages().list(userId='me', pageToken=next_page_token, maxResults=1000).execute()

	messages = result.get('messages', [])
	NEXT_TOKEN = result.get('nextPageToken') if 'nextPageToken' in result else None
	
	if not messages:
		print('No messages found')
	
	return messages


def _list_labels(service):
	labels = service.users().labels().list(userId='me').execute()
	labels = labels.get('labels', [])
	
	if not labels:
		print('No labels found')
	else:
		print('Labels:')
		for label in labels:
			print(label['name'])
	
	return labels


def _get_message(service, id):
	result = service.users().messages().get(userId='me', id=id).execute()

	return result


def _delete_all(client, ids):
	print('Deleting {} new msgs'.format(len(ids)))
	result = client.users().messages().batchDelete(userId='me', body={'ids': ids}).execute()
	
	return result


def _process_deletes(service, messageids):
	
	delete_senders = []
	delete_ids = []
	visited = []
	key = None
	
	file_junk = open('./junkIds.txt', 'r+')
	file_imp = open('./impIds.txt', 'r+')

	while True:
		line = file_junk.readline()
		if not line:
			break
		res = re.search(r'<.*?>', line.strip())
		if res:	
			delete_senders.append(res.group())

	while True:
		line = file_imp.readline()
		if not line:
			break
		res = re.search(r'<.*?>', line.strip())
		if res:
			visited.append(res.group())
	
	for id in messageids:
		msg = _get_message(service, id['id'])
		if msg is not None:
			# import pdb; pdb.set_trace()
			# key = msg['payload']['headers'][15]['name']
			if key != 'From':
				for h in msg['payload']['headers']:
					if h['name'] == 'From':
						sender = h['value']
			else:
				sender = msg['payload']['headers'][15]['value']

			sender2 = re.search(r'<.*?>', sender)
			if sender2:
				sender = sender2.group()
				#domain = sender.split('@')[1]
				#domain = sender if domain in COMMON_DOMAINS else domain

			if sender not in delete_senders and sender not in visited:
				print('Message snippet: {}'.format(msg['snippet']))
				print('Received from: {}'.format(sender))
				ans = input('Do you want to delete all messages from this sender? (y/n)')
				if ans == 'y' :
					delete_senders.append(sender)
					delete_ids.append(msg['id'])
					file_junk.write(sender + '\n')
				else:
					visited.append(sender)
					file_imp.write(sender + '\n')
			elif sender in delete_senders:
				print('Deleting sender: {}'.format(sender))
				delete_ids.append(msg['id'])
			else:
				print('Skipping sender: {}'.format(sender))
	
		if len(delete_ids) >= BATCH_SIZE:
			result = _delete_all(service, delete_ids)
			delete_ids = []

	if file_junk:
		file_junk.close()
	if file_imp:
		file_imp.close()


def main():
	service = _build_client()

	#labels = _list_labels(service)

	messageids = _list_messages(service, NEXT_TOKEN)

	_process_deletes(service, messageids)

	while NEXT_TOKEN is not None:
		print('Processing next page from token id {}'.format(NEXT_TOKEN))
		messageids = _list_messages(service, NEXT_TOKEN)
		_process_deletes(service, messageids)


if __name__ == '__main__':
	main()

