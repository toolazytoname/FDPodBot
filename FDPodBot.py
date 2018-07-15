# coding=utf-8
import os
import subprocess
import logging
import logging.config
import time
from datetime import datetime
import sched
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from configparser import ConfigParser
import json


cfg = ConfigParser()
schduler = sched.scheduler(time.time, time.sleep)

def main():
    # Configure the logging system
    logging.config.fileConfig('logconfig.ini')
    cfg.read('FDPodBot.ini')
    sched()
    # lint()

def sched():
    now = datetime.now()
    sched_time = datetime(now.year, now.month, now.day, cfg.getint('sched', 'sched_hour'), cfg.getint('sched', 'sched_minute'), cfg.getint('sched', 'sched_second'))
    if sched_time < now:
        sched_time = sched_time.replace(day=now.day+1)
    schduler.enterabs(sched_time.timestamp(), 0, lint)
    schduler.run()

def lint():
    schduler.enter(cfg.getfloat('sched', 'sched_duration'), 0, lint)
    git_source_list = json.loads(cfg.get('git', 'git_sources'))

    # git clone
    git_clone_shell_command_list = list()
    for git_source in git_source_list:
        git_clone_shell_command_list.append('git clone ' + git_source + ';')
    git_clone_shell_command = ' '.join(str(git_clone_shell_command) for git_clone_shell_command in git_clone_shell_command_list)
    run_shell(git_clone_shell_command)

    # cd; pull;checkout;lint
    current_directory = os.getcwd()
    # repo_directory_list = (os.path.join(current_directory, repo_directory)
    #                       for repo_directory in os.listdir(current_directory)
    #                       if os.path.isdir((os.path.join(current_directory, repo_directory))) and repo_directory.startswith('B'))
    repo_directory_list = list()
    for repo_directory in os.listdir(current_directory):
        if os.path.isdir((os.path.join(current_directory, repo_directory))) and repo_directory.startswith('B'):
            repo_directory_list.append(os.path.join(current_directory, repo_directory))

    git_develop_branch_dic = json.loads(cfg.get('git', 'git_develop_branch'))

    lint_shell_command_list = list()
    for repo_directory in repo_directory_list:
        (repo_directory_dirname, repo_directory_filename) = os.path.split(repo_directory)
        checkout_command = ''
        if git_develop_branch_dic.__contains__(repo_directory_filename):
            checkout_command = 'git checkout ' + git_develop_branch_dic[repo_directory_filename] + ';'
        lint_shell_command_list.append(
            'cd ' + repo_directory + ';git pull;' + checkout_command + "git log -1;git branch;pod lib lint --sources='http://gitlab.bitautotech.com/WP/Mobile/IOS/Specs.git,https://github.com/CocoaPods/Specs.git' --allow-warnings --use-libraries;")

    for lint_shell_command in lint_shell_command_list:
        out_text = run_shell(lint_shell_command)
        if 'passed validation' not in out_text:
            alarm(lint_shell_command, out_text)
        else:
            log_lint(lint_shell_command, out_text)



def run_shell(shell_command):
    try:
        out_bytes = subprocess.check_output(shell_command, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        out_bytes = e.output
        # code = e.returncode
    finally:
        out_text = out_bytes.decode('utf-8')
        logging.debug('out_text is: %r', out_text)
        return out_text


def alarm(lint_shell_command, log):
    message = ' [Alarm] lint_shell_command :{0} \n log is:{1}\n not passed validation'.format(lint_shell_command,log)
    logging.critical(' %s ', message)
    mail(message)

def log_lint(lint_shell_command,log):
    logging.info('lint_shell_command : %s passed validation', lint_shell_command)

def mail(content):
    result = True
    mail_host = cfg.get('mail', 'mail_host')
    mail_user = cfg.get('mail', 'mail_user')
    mail_pass = cfg.get('mail', 'mail_pass')
    mail_sender = cfg.get('mail', 'mail_sender')
    mail_smtp_ssl_port = cfg.getint('mail', 'mail_smtp_ssl_port')
    mail_subject = cfg.get('mail', 'mail_subject')
    mail_receivers = json.loads(cfg.get('mail', 'mail_receivers'))
    try:
        message = MIMEText('pod lib lint 验证有误\n' + content, 'plain', 'utf-8')
        message['From'] = formataddr(['FDPodBot', mail_sender])
        message['To'] = ','.join(mail_receivers)
        message['Subject'] = mail_subject
        server = smtplib.SMTP_SSL(mail_host, mail_smtp_ssl_port)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_user, mail_receivers, message.as_string())
        server.quit()
        logging.critical('邮件发送成功')
    except smtplib.SMTPException:
        logging.critical('无法发送邮件')
        result = False
    return result

if __name__=='__main__':
    main()