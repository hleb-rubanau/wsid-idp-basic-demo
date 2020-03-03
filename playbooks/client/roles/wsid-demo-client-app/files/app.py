from flask import Flask, jsonify, request, render_template
import os
import subprocess
import requests
from paramiko.client import SSHClient, RejectPolicy
from paramiko.ed25519key import Ed25519Key
PASSWORD_FILE_LOCATION=os.getenv("WSID_PASSWD_FILE")
KEY_FILE_LOCATION=os.getenv("WSID_KEY_FILE")
WSID_IDENTITY=os.getenv('WSID_IDENTITY') # https://thisdomain/<username>
DEMO_UPSTREAM=os.getenv("DEMO_UPSTREAM")
DEMO_SSH_USER=os.getenv("DEMO_SSH_USER")


# to be re-read on reload and NOT exposed as ENV vars
with open(PASSWORD_FILE_LOCATION,'r') as pwdfile:
    SECRET_PASSWORD=pwdfile.read().strip()
with open(KEY_FILE_LOCATION,'r') as keyfile:
    SECRET_SSH_KEY_BODY=keyfile.read().strip()
    SECRET_SSH_KEY=Ed25519Key(data=SECRET_SSH_KEY_BODY)

app = Flask(__name__)

# TBD: move to core library
def load_remote_host_keys(host, hostkeys):
    logging.getLogger('wsid')

    host_keys_endpoint = "https://{host}/.wsid/ssh_host_ed25519.pub"
    logger.info("Fetching public keys from {host_keys_endpoint")
    
    keys_body = requests.get(host_keys_endpoint).text
    for hostkey in keys_body.split("\n"):
        if not hostkey:
            continue
        logger.debug(f"Adding {host} {hostkey}")
        keytype,keybody=hostkey.split(" ")
        hostkeys.add( host, keytype, keybody )



class LogCapture(object):
    def __init__(self):
        self.messages = []

    def write(self, str):
        self.messages.append(str)

    def flush(self):
        pass

    def __str__(self):
        return "\n".join(self.messages)


def initialize_log_capturer(logger):
    capturer = LogCapture()
    handler = logging.StreamHandler(capturer)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
  
    logger=logging.getLogger() 
    logger.addHandler(handler)

    return (capturer, lambda x: logger.removeHandler(handler))

@app.route("/")
def index():
    return render_template('index.html', 
                            upstream=DEMO_UPSTREAM)

@app.route("/test/http",methods=["POST"])
def test_http():

    logger=logging.getLogger()
    capturer, log_teardown = initialize_log_capturer( logger )

    target_endpoint = f"https://{DEMO_UPSTREAM}/test/whoami"
    auth=(WSID_IDENTITY, SECRET_PASSWORD)              

    logger.info(f"Testing server-to-server http call, API endpoint is {target_endpoint}, auth is {auth}")

    try:
        result=requests.post(target_endpoint, auth=auth)    
        logger.info(f"result: {result.status_code}, {result.text}")
    except e:
        logger.error(f"FAILURE: {e}")

    log_teardown()
    return jsonify(capturer.messages)

@app.route("/test/ssh", methods=["POST"])
def test_ssh():
    logger=logging.getLogger('wsid')
    capturer, log_teardown = initialize_log_capturer( logger )
    
    ssh_endpoint=f"{DEMO_SSH_USER}@{DEMO_UPSTEAM}"

    logger.info(f"Testing SSH endpoint {ssh_endpoint} with temporary key")
    try:
        with SSHClient() as ssh:
            hostkeys = ssh.get_host_keys()
            load_remote_host_keys(DEMO_UPSTREAM, hostkeys)

            logger.info("Initiating connection")

            ssh.connect(DEMO_UPSTREAM,
                        username=DEMO_SSH_USER,
                        look_for_keys=False,
                        allow_agent=False,
                        pkey=SECRET_SSH_KEY)


                    
            logger.info(f"Connection successful: {ssh._transport.get_banner()}")
            ssh.close()
    except e:
        logger.error(f"FAILURE: {e}")
        
    log_teardown()
    return jsonify(messages)
