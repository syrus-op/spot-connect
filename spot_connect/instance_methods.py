"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for launching an AWS spot instance - instance_methods.py: 

The instance_methods sub-module contains functions that interact with existing 
instances, like running a script/command, uploading a file or even terminating
the instance. 

MIT License 2020
"""

import sys, boto3, os
from spot_connect import ec2_methods, sutils, interactive

def run_script(instance, user_name, script, cmd=False, port=22, kp_dir=None, return_output=False, combine_error_stream=True):
    '''
    Run a script on the the given instance 
    __________
    parameters
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - script : string. ".sh" file or linux/unix command (or other os resource) to execute on the instance command line 
    - cmd : if True, script string is treated as an individual argument 
    - port : port to use to connect to the instance 
    '''
    
    if kp_dir is None: 
        kp_dir = sutils.get_default_kp_dir()

    if cmd: 
        commands = script
    else:   
        commands = open(script, 'r').read().replace('\r', '')

    client = ec2_methods.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=user_name,port=port)
    
    session = client.get_transport().open_session()
    if combine_error_stream: session.set_combine_stderr(True)                  # Combine the error message and output message channels
    session.exec_command(commands)                                             # Execute a command or .sh script (unix or linux console)
    
    if return_output:
        output = ''
        error_output = ''
    
    exit_status = session.recv_exit_status()
    print(f"******** Exit Code - {exit_status} ************")
    if exit_status <=0:
        run_stat = True
    else:
        run_stat = False

    stdout = session.makefile()                                                # Collect the output 
    

    try:
        for line in stdout:
            if return_output: output+=line.rstrip()+'\n'
            else: print(line.rstrip(), flush=True)                             # Show the output 
    
    except (KeyboardInterrupt, SystemExit):
        print(sys.stderr, 'Ctrl-C, stopping', flush=True)                      # Keyboard interrupt 
    
    if not combine_error_stream:
        stderr = session.makefile_stderr()                                     # Collect the error output 
        try:
            for line in stderr:
                if return_output: error_output+=line.rstrip()+'\n'
                else: print(line.rstrip(), flush=True)                         # Show the error output

        except (KeyboardInterrupt, SystemExit):
            print(sys.stderr, 'Ctrl-C, stopping', flush=True)                  # Keyboard interrupt 
    client.close()                                                             # Close the connection    

    if return_output: 
        if combine_error_stream: return run_stat, output
        return run_stat, output, error_output, exit_status
    else: return run_stat


def active_shell(instance, user_name, port=22, kp_dir=None): 
    '''
    Leave a shell active
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - port : port to use to connect to the instance 
    '''    

    if kp_dir is None: 
        kp_dir = sutils.get_default_kp_dir()
    
    client = ec2_methods.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=user_name,port=port)

    console = client.invoke_shell()                                            
    console.keep_this = client                                                

    session = console.get_transport().open_session()
    session.get_pty()
    session.invoke_shell()

    try:
        interactive.interactive_shell(session)

    except: 
        print('Logged out of interactive session.')

    session.close() 
    return True 


def upload_to_ec2(instance, user_name, files, remote_dir='.', kp_dir=None, verbose=False):
    '''
    Upload files directly to an EC2 instance. Speed depends on internet connection and not instance type. 
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - files : string or list of strings. single file, list of files or directory to upload. If it is a directory end in "/" 
    - remote_dir : '.'  string.The directory on the instance where the files will be uploaded to 
    '''

    if kp_dir is None: 
        kp_dir = sutils.get_default_kp_dir()

    client = ec2_methods.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=user_name,port=22)
    if verbose:
        print('Connected. Uploading files...')
    stfp = client.open_sftp()

    try: 
    	for f in files: 
            if verbose:
                print('Uploading %s' % str(os.path.split(f)[-1]))
            stfp.put(f, os.path.join(remote_dir, os.path.split(f)[-1]), callback=sutils.printTotals, confirm=True)

    except Exception as e:
        raise e

    if verbose:
        print('Uploaded to %s' % remote_dir)
    return True 


def download_from_ec2(instance, username, get, put='.', kp_dir=None):
    '''
    Download files directly from an EC2 instance. Speed depends on internet connection and not instance type. 
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instance method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - get : str or list of str. File or list of file paths to get from the instance 
    - put : str or list of str. Folder to place the files in `get` 
    '''

    if kp_dir is None: 
        kp_dir = sutils.get_default_kp_dir()

    client = boto3.client('ec2', region_name='us-west-2')
    client = ec2_methods.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=username,port=22)

    stfp = client.open_sftp()

    for idx, file in enumerate(get): 
        try: 
            stfp.get(file,put[idx], callback=sutils.printTotals)
        except Exception as e: 
            print(file)
            raise e
    return True 


def terminate_instance(instance_id):
    '''Terminate  an instance using the instance ID'''
    
    if type(instance_id) is str: 
        instances = [instance_id]

    elif type(instance_id) is list: 
        instances = instance_id

    else: 
        raise Exception('instance_id arg must be str or list')

    ec2 = boto3.resource('ec2')
    ec2.instances.filter(InstanceIds=instances).terminate()
