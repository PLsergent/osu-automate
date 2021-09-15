from __future__ import print_function
import os.path
import socket
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import googleapiclient
import google_auth_httplib2
import httplib2

class GoogleAuth:
    def __init__(self):
        self.scopes =  ['https://www.googleapis.com/auth/drive']
        self.creds = None
        self.flow = Flow.from_client_secrets_file(
                    'credentials.json', self.scopes, redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        self.service = self.authenticate()
    
    def build_request(self, http, *args, **kwargs):
        new_http = google_auth_httplib2.AuthorizedHttp(self.creds, http=httplib2.Http())
        return googleapiclient.http.HttpRequest(new_http, *args, **kwargs)

    def display_prompt(self):
        # Tell the user to go to the authorization URL.
        auth_url, _ = self.flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')

        print('Please go to this URL: {}'.format(auth_url))

        # The user will get an authorization code. This code is used to get the
        # access token.
        code = input('Enter the authorization code: ')
        self.flow.fetch_token(code=code)
        self.creds = self.flow.credentials

    def authenticate(self):
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', self.scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired:
                try:
                    self.creds.refresh(Request())
                except:
                    print("Error: refresh_token expired.")
                    self.display_prompt()

                    # Save the credentials for the next run
                    with open('token.json', 'w') as token:
                        token.write(self.creds.to_json())
            else:
                self.display_prompt()

            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(self.creds.to_json())

        print('Authentication done!')

        # Set timeout to 600 seconds since uploads can take a while
        socket.setdefaulttimeout(600)
        return build('drive', 'v3', requestBuilder=self.build_request, credentials=self.creds)