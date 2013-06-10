from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from django.utils import simplejson as json
#from appengine_utilities import sessions
from gaesessions import get_current_session
from google.appengine.ext import db

import logging
import endpoints
import os
import urllib
from account import Account

def get_target_url():
    params = get_params()
    return endpoints.AUTH_ENDPOINT + '?' + urllib.urlencode(params)
    
def get_current_account():
    session = get_current_session()
    if 'user_id' in session:
        return Account.get_by_key_name(session['user_id'])
        
def get_params():
    return {
              'scope':endpoints.SCOPE,
              'state':'/',
              'redirect_uri':'https://' + os.environ['HTTP_HOST'] + '/oauthcallback',
              'response_type':'token',
              'client_id':endpoints.CLIENT_ID
             }

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.redirect('/step/1')

class CallbackHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write(template.render('templates/tokenspewer.html', {}))

class AcceptTokenHandler(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        session.regenerate_id()
        a_t = self.request.get('access_token')
        session['a_t'] = a_t
        
        # check the token audience using exact match (TOKENINFO)
        url = endpoints.TOKENINFO_ENDPOINT + '?access_token=' + a_t
        tokeninfo = json.loads(urlfetch.fetch(url).content)
        
        session['token_info'] = tokeninfo
        
        if(tokeninfo['audience'] != endpoints.CLIENT_ID):
          self.error(400)
          return
        
        if(int(tokeninfo['expires_in']) < 1):
          self.error(400)
          return
          
        # get the user profile information (USERINFO)
        userinfo = json.loads(urlfetch.fetch(endpoints.USERINFO_ENDPOINT,
                                             headers={'Authorization': 'OAuth ' + a_t}).content)
        user_id = userinfo['id']
        session['user_id'] = user_id 
        session['user_info'] = userinfo
        
        # compose the URL returned in the callback (for the view)
        session['response_with_token'] = 'https://' + os.environ['HTTP_HOST'] + '/oauthcallback#' + self.request.query_string
        
        acct = Account.get_by_key_name(user_id)
      
        acct = Account(
                        key_name=user_id, 
                        name=userinfo.get('name'),
                        user_info=json.dumps(userinfo), 
                        family_name=userinfo.get('family_name'),
                        locale=userinfo.get('locale')
                        gender=userinfo.get('gender'),
                        email=userinfo.get('email'),
                        given_name=userinfo.get('given_name'),
                        google_account_id=userinfo.get('id'),
                        verified_email=userinfo.get('verified_email'),
                        link=userinfo.get('link'),
                        picture=userinfo.get('picture')
                      )
                          
        acct.access_token = a_t
        acct.put()      
        
class StepHandler(webapp.RequestHandler):
    def get(self, stepNum):
        if int(stepNum) > 4 or int(stepNum) < 1:
            self.error(400)
            return
        
        session = get_current_session()
        
        templateInfo = {
                            'targetUrl': get_target_url(), 
                            'session': session, 
                            'params': get_params(), 
                            'stepNum': stepNum, 
                            'account':get_current_account(), 
                            'template_name': 
                            'step%s.html' % stepNum 
                        }
        
        self.response.out.write(template.render('templates/stepTemplate.html', templateInfo))
    
class LogoutHandler(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        logging.info('Session: %s' % session)
        session.terminate()
        self.redirect('/')   

class LogoutAndRemoveHandler(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        logging.info('Session: %s' % session)
        user_id = session['user_id'] 
        account = Account.get_by_key_name(user_id)
        session.terminate()
        account.delete()
        self.redirect('/') 
        
        