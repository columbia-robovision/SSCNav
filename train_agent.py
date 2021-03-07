from SCNav_agent import SCNavAgent, name2id
from utils.utils import d3_41_colors_rgb, ScalarMeanTracker

import torch

import random
import numpy as np
import argparse
import cv2
import shutil
import os
from tensorboardX import SummaryWriter
from tqdm import tqdm
import json

parser = argparse.ArgumentParser()

parser.add_argument("--title", type=str, required=True)
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--device", type=str, default="cuda")
parser.add_argument("--config_paths", type=str,
        default="./configs/agent_train.yaml")
parser.add_argument("--flip", type=float, default=0.5)
parser.add_argument("--seg_threshold", type=int, default=5000)
parser.add_argument("--pano", type=bool, default=False)
parser.add_argument("--user_semantics", type=bool, default=False)
parser.add_argument("--seg_pretrained", type=str, default="")
parser.add_argument("--cmplt", type=bool, default=False)
parser.add_argument("--cmplt_pretrained", type=str, default="")
parser.add_argument("--conf", type=bool, default=False)
parser.add_argument("--conf_pretrained", type=str, default="")
parser.add_argument("--targets", type=str,
        default="bed|toilet|table|sink|sofa|door|shower|counter")
parser.add_argument("--aggregate", type=bool,
        default=True)
parser.add_argument("--memory_size", type=int, default=5)
parser.add_argument("--num_channel", type=int, default=41)
parser.add_argument("--success_threshold", type=float, default=1.)
parser.add_argument("--collision_threshold", type=float, default=0.125)
parser.add_argument("--ignore", type=str, default='17|40')
parser.add_argument("--Q_pretrained", type=str, default="")
parser.add_argument("--offset", type=float, default=0.3)
parser.add_argument("--floor_threshold", type=float, default=0.1)
parser.add_argument("--lr", type=float, default=0.01)
parser.add_argument("--momentum", type=float, default=0.9)
parser.add_argument("--weight_decay", type=float, default=0.0001)
parser.add_argument("--gamma", type=float,default=0.99)
parser.add_argument('--batch_size', type=int, default=32)
parser.add_argument("--buffer_size", type=int, default=10000)
parser.add_argument("--height", type=float, default=1.25)
parser.add_argument("--area_x", type=float, default=6.)
parser.add_argument('--area_z', type=float, default=6.)
parser.add_argument("--h", type=int, default=128)
parser.add_argument('--w', type=int, default=128)
parser.add_argument("--h_new", type=int, default=128)
parser.add_argument("--w_new", type=int, default=128)
parser.add_argument('--max_step', type=int, default=100)
parser.add_argument('--navigable_base', type=str, default="1|40")
parser.add_argument("--max_transition", type=int, default=100000)
parser.add_argument("--start_replay", type=int, default=1000)
parser.add_argument("--update_target", type=int, default=1000)
parser.add_argument("--start_eps", type=float, default=1.)
parser.add_argument("--end_eps", type=float, default=0.01)
parser.add_argument("--fix_transition", type=int, default=6000)
parser.add_argument("--success_reward", type=float, default=10.)
parser.add_argument("--step_penalty", type=float, default=-0.01)
parser.add_argument("--approach_reward", type=float, default=1.)
parser.add_argument("--collision_penalty", type=float, default=-0.25)
parser.add_argument("--save_dir", type=str,
        default="/local/crv/yiqing/result")
parser.add_argument("--save_interval", type=int,
        default=10000)
parser.add_argument("--log_dir", type=str, default="/local/crv/yiqing/run")
parser.add_argument("--train_thin", type=int, default=6)
parser.add_argument("--loss_thin", type=int, default=5)
parser.add_argument("--train_vis", type=int, default=1000) 
parser.add_argument("--scene_types", type=str, default="bathroom|bedroom|dining room|kitchen|living room|laundryroom/mudroom|familyroom/lounge")
parser.add_argument("--max_dist", type=float, default=25.)
parser.add_argument("--double_dqn", type=bool, default=True)
parser.add_argument("--TAU", type=float, default=0.001)
parser.add_argument("--soft_update", type=bool, default=False)
parser.add_argument("--count", type=int)
parser.add_argument("--preconf", type=bool, default=False)
parser.add_argument("--load_json", type=str, default="")
parser.add_argument("--checkpoint", type=str, default="")
parser.add_argument("--shortest", type=bool, default=False)
parser.add_argument("--tsplit", type=int, default=-1)

def adjust_learning_rate(optimizer, timestep, learning_rate, learning_rate_decay_steps):
    lr = learning_rate
    for t in learning_rate_decay_steps:
        if timestep >= t:
            lr *= 0.1
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr
    return lr

def main():
    args = parser.parse_args()
    assert args.title in ['debug', 'random', 'single', 's', 's_c', 's_cf', 's_cu', 'ps', 'ps_cu',
            'ss', 'ss_c', 'ss_cu', 'ss_new', 'ss_c_new', 'ss_cu_new',
            's_new', 's_c_new', 's_cu_new', 'ss_1', 'ss_c_1', 'ss_cu_1', 's_1',
            's_c_1', 's_cu_1', 's_cu_2', 's_cu_3', 's_2', 's_3', 's_c_3',
            's_c_4', 's_cu_3', 's_chal', 's_c_chal', "s_cu_chal",
            's_shortest', 's_c_shortest', 's_cu_shortest', 'fake_conf',
            'discrete', 's_cu_chal_2', 'discrete_2', 's_cu_chal_3',
            's_cu_chal_att', 's_cu_chal_4', 's_cu_chal_5', 's_cu_chal_6', 'fake_conf_2',
            's_chal_final', 's_cu_chal_final', 'sscnav', 'sscnav_cf',
            'sscnav_c', 'sscnav_path', 'redo_cu'], "Illegal exp id"
    new_eval=False
    fake_conf=False
    discrete=False
    att = False
    rc = False
    unconf = False
    full_map = False
    if args.title ==  'debug':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        full_map = True
        args.shortest = True 
        args.seg_pretrained = "/local/crv/yiqing/result/train_seg/10.pth"

        args.config_paths = './configs/agent_test.yaml'

    if args.title == 'random':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 'single':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 's':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 's_c':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
    elif args.title == 's_cu':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
    elif args.title == 's_1':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 's_c_1':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
    elif args.title == 's_c_3':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
    elif args.title == 's_c_chal':
        args.Q_pretrained = ''
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
        new_eval = True
    elif args.title == 's_cu_1':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
    elif args.title == 's_cu_2':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
    elif args.title == 's_cu_chal':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 's_cu_chal_2':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_2/4_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 's_cu_chal_3':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 's_cu_chal_4':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 'redo_cu':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 'sscnav_cf':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = False
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.conf = False
        args.pano = False
        new_eval = True
        full_map = True

    elif args.title == 'sscnav_c':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
        new_eval = True
        full_map = True

    elif args.title == 'sscnav':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        full_map = True
        args.seg_pretrained = "/local/crv/yiqing/result/train_seg/10.pth"
    elif args.title == 'sscnav_path':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        full_map = True
        args.shortest = True
        args.max_step = 500
        args.seg_pretrained = "/local/crv/yiqing/result/train_seg/10.pth"
    elif args.title == 's_cu_chal_att':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        att = True
    elif args.title == 's_cu_chal_5':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        rc = True
    elif args.title == 's_cu_chal_6':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_5/20_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 's_cu_chal_final':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_5/20_fd.pth'
        args.pano = False
        new_eval = True
        
    elif args.title == 'fake_conf':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained = ''
        args.pano = False
        new_eval = True
        fake_conf = True
    elif args.title == 'fake_conf_2':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained = ''
        args.pano = False
        new_eval = True
        fake_conf = True
        unconf = True
    elif args.title == 'discrete_2':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_2/4_fd.pth'
        args.pano = False
        new_eval = True
        discrete = True
    elif args.title == 'discrete':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.targets = "bed|toilet|table|sink|sofa|door|shower|counter"
        args.max_dist = float("inf")
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_4/14_fd.pth'
        args.pano = False
        new_eval = True
        discrete = True
    elif args.title == 's_2':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 's_chal':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
        new_eval = True
    elif args.title == 's_chal_final':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
        new_eval = True
    elif args.title == 's_3':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = False
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
    elif args.title == 's_shortest':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = False
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        new_eval = True
    elif args.title == 's_c_4':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
    elif args.title == 's_c_shortest':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        new_eval = True
        args.max_step = 500
    elif args.title == 's_cu_3':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        args.max_step = 500
    elif args.title == 's_cu_shortest':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.max_dist = float("inf")
        args.shortest = True
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        new_eval = True
        args.max_step = 500

    elif args.title == 's_new':
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.Q_pretrained = '/local/crv/yiqing/result/ss/1100.pth'
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 's_c_new':
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.Q_pretrained = '/local/crv/yiqing/result/s_c/60000.pth'
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = False
        args.pano = False
    elif args.title == 's_cu_new':
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.Q_pretrained = "/local/crv/yiqing/result/s_cu/60000.pth"
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False

    elif args.title == 's_cf':
        args.Q_pretrained = "/local/crv/yiqing/result/s_cu/60000.pth"
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = False
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.start_eps = 0.01
        args.preconf = True


    elif args.title == 'ps':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = False
        args.conf = False
        args.pano = True
    elif args.title == 'ps_cu':
        args.Q_pretrained = ""
        args.user_semantics = False
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized/17_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf/5_fd.pth'
        args.pano = True
    elif args.title == 'ss':
        args.Q_pretrained = "/local/crv/yiqing/result/s/60000.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 'ss_c':
        args.Q_pretrained = "/local/crv/yiqing/result/s_c/60000.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = False
        args.pano = False

    elif args.title == 'ss_cu':
        args.Q_pretrained = "/local/crv/yiqing/result/s_cu/60000.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_seg/5_fd.pth'
        args.pano = False
    elif args.title == 'ss_new':
        args.Q_pretrained = "/local/crv/yiqing/result/ss/1100.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 'ss_c_new':
        args.Q_pretrained = "/local/crv/yiqing/result/s_c/60000.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = False
        args.pano = False

    elif args.title == 'ss_cu_new':
        args.Q_pretrained = "/local/crv/yiqing/result/s_cu/60000.pth"
        args.lr = 0.001
        args.weight_decay = 0.00001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_seg/5_fd.pth'
        args.pano = False
    elif args.title == 'ss_1':
        args.Q_pretrained = ""
        args.lr = 0.01
        args.weight_decay = 0.0001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = False
        args.conf = False
        args.pano = False
    elif args.title == 'ss_c_1':
        args.Q_pretrained = ""
        args.lr = 0.01
        args.weight_decay = 0.0001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = False
        args.pano = False

    elif args.title == 'ss_cu_1':
        args.Q_pretrained = "/local/crv/yiqing/result/s_cu/60000.pth"
        args.lr = 0.01
        args.weight_decay = 0.0001
        args.user_semantics = True
        args.seg_pretrained = '/local/crv/yiqing/result/train_seg/10.pth'
        args.cmplt = True
        args.cmplt_pretrained\
        = '/local/crv/yiqing/result/train_cmplt_resized_seg/16_cd.pth'
        args.conf = True
        args.conf_pretrained\
                = '/local/crv/yiqing/result/train_conf_seg/5_fd.pth'
        args.pano = False


    #assert args.title == 'debug', "fix action bug"
    #args.max_step = 10
    #args.start_replay = 40.
    #args.config_paths = 'configs/agent_test.yaml'
    #print(bool(str(args.soft_update)))
    #assert False, "Category level success/spl>1/5"
    #assert False, "Fix episode not terminating bug?"
  #  print(bool(str(args.double_dqn)))
  #  assert False, "Pause"
  #  print(bool(args.cmplt))
  #  assert False, "Pause"
    
   # assert not args.user_semantics, "Semantic input debug"
   # assert not args.cmplt, "Cmplt debug"
   # assert not args.conf, "conf debug"
    if args.checkpoint != "":
        ckp = torch.load(args.checkpoint)

        save_dir = ckp['save_dir']
        log_dir = ckp['log_dir']
    else:
        save_dir = os.path.join(args.save_dir, args.title)
        if os.path.exists(save_dir):
            assert False, "Dir exists!"
        os.mkdir(save_dir)
        log_dir = os.path.join(args.log_dir, args.title)
        if os.path.exists(log_dir):
            assert False, "Dir exists!"
    log_writer = SummaryWriter(log_dir = log_dir)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    agent = SCNavAgent(
            preconf = args.preconf,
            device = torch.device(args.device),
            #device = torch.device("cpu"),
            min_dist = 0.,
            config_paths = args.config_paths,
            flip = args.flip,
            save_dir = save_dir,
            pano = bool(args.pano),
            #pano = False,
            user_semantics = bool(args.user_semantics),
            seg_pretrained = args.seg_pretrained,
            cmplt = bool(args.cmplt),
            cmplt_pretrained = args.cmplt_pretrained,
            conf = bool(args.conf),
            conf_pretrained = args.conf_pretrained,
            targets = args.targets,
            aggregate = bool(args.aggregate),
            #aggregate = True,
            memory_size = args.memory_size,
            num_channel = args.num_channel,
            success_threshold = args.success_threshold,
            collision_threshold = args.collision_threshold,
            ignore = args.ignore,
            training = True,
            Q_pretrained = args.Q_pretrained,
            #Q_pretrained = '../result/1.pth',
            offset = args.offset,
            floor_threshold = args.floor_threshold,
            lr = args.lr,
            momentum = args.momentum,
            weight_decay = args.weight_decay,
            gamma = args.gamma,
            batch_size = args.batch_size,
            #batch_size = 1,
            buffer_size = args.buffer_size,
            height = args.height,
            area_x = args.area_x,
            area_z = args.area_z,
            h = args.h,
            w = args.w,
            h_new = args.h_new,
            w_new = args.w_new,
            max_step = args.max_step,
            #max_step = 5,
            navigable_base = args.navigable_base,
            success_reward = args.success_reward,
            step_penalty = args.step_penalty,
            approach_reward = args.approach_reward,
            collision_penalty
            = args.collision_penalty,
            #max_dist = args.max_dist,
            max_dist = float("inf"),
            scene_types = args.scene_types,
            double_dqn = args.double_dqn,
            TAU = args.TAU,
            seg_threshold = args.seg_threshold,
            shortest = args.shortest,
            current_position = None if args.checkpoint=='' else ckp['current_position'],
            new_eval=new_eval,
            fake_conf=fake_conf,
            discrete=discrete,
            att=att,
            rc=rc,
            unconf=unconf,
            full_map=full_map)


    
    train_thin = args.train_thin
    if args.checkpoint == '':
        global_step = 0
        train_scalars = {'all': ScalarMeanTracker()}
        loss_q_reward = ScalarMeanTracker()
        ep_id = 0
    else:
        agent.optimizer.load_state_dict(ckp['optimizer_state_dict'])
        agent.Q_t.load_state_dict(ckp['Q_t_state_dict'])
        agent.Q.load_state_dict(ckp['Q_state_dict'])
    
        global_step = ckp['global_step']
        train_scalars = ckp['train_scalars']
        loss_q_reward = ckp['loss_q_reward']
        ep_id = ckp['ep_id']
    pbar = tqdm(total=args.max_transition)
    for k in range(global_step):
        pbar.update(1)

    #targets = [10, 17, 4, 14, 9, 3, 24, 22, 25]
    targets = [name2id[tg] for tg in agent.targets]
    while global_step < args.max_transition:

        #agent.reset()
        #assert args.title == 'debug', "don't forget to delete this part"
        #if args.title == 'debug':
        #    assert False, "debugging!"
            #  with open('test.json', 'r') as f:
          #      config = json.load(f)['1']
          #  agent.reset_config(config)
        #else:
        agent.reset(agent.targets[ep_id % len(agent.targets)])
        assert agent.target == targets[ep_id % len(agent.targets)], "False"
        while not agent.done:
            # eps: balance exploration & exploitation

            eps_threshold = None
            if global_step < args.start_replay:
                eps_threshold = args.start_eps
            elif global_step < args.fix_transition:    
                eps_threshold = args.start_eps - (args.start_eps - args.end_eps) * \
                    (global_step - args.start_replay) / (args.fix_transition - args.start_replay)
            else:
                eps_threshold = args.end_eps

            if (global_step+1) % args.train_vis == 0:
                cv2.imwrite(os.path.join(save_dir, "%s_old_obs_%s.png"
                    % (global_step + 1, agent.target)),
                    d3_41_colors_rgb[torch.argmax(agent.state[0,
                        :agent.num_channel,...] , dim=0)])
                if args.cmplt:
                    if args.conf or fake_conf:
                        cv2.imwrite(os.path.join(save_dir, "%s_conf_obs_%s.png"
                            % (global_step + 1, agent.target)),
                            255. * agent.conf_obs[0,0].numpy())
                cv2.imwrite(os.path.join(save_dir, "%s_rgb_%s.png"
                    % (global_step + 1, agent.target)),
                    agent.get_observations()['rgb'][..., [2, 1, 0]])


            dreward = agent.step(eps_threshold)
            

            torch.cuda.empty_cache()

            if (global_step + 1) % args.train_vis == 0:
                if not discrete:
                    cmap = agent.q_map.numpy()
                    if np.max(cmap) == np.min(cmap):
                        cmap = np.zeros(cmap.shape).astype(np.uint8)
                    else:
                        cmap = (cmap - np.min(cmap)) / (np.max(cmap)
                                - np.min(cmap)) * 255.
                        cmap = cmap.astype(np.uint8)
                    cmap = cv2.cvtColor(cmap, cv2.COLOR_GRAY2BGR)
                    cmap = cv2.applyColorMap(cmap, cv2.COLORMAP_JET)
                    cv2.circle(cmap, (agent.action[1], agent.action[0]), 5, (20,
                        20, 20), -1)
                    cv2.imwrite(os.path.join(save_dir, "%s_q_map_%s.png"
                        % (global_step + 1, agent.target)),
                        cmap)

                cv2.imwrite(os.path.join(save_dir, "%s_new_obs_%s.png"
                   % (global_step + 1, agent.target)),
                    d3_41_colors_rgb[torch.argmax(agent.state[0,
                      :agent.num_channel,...] , dim=0)])
               

            global_step += 1
            pbar.update(1)


            if global_step <= args.start_replay:
                continue

            dloss = agent.train_Q()

            status = {
               "avg_loss": dloss,
               "avg_reward": dreward,
               "avg_q": float(torch.max(agent.q_map)),
               }
            loss_q_reward.add_scalars(status)

            if global_step % args.loss_thin == 0:
                tracked_means = loss_q_reward.pop_and_reset()
                for k in tracked_means:
                    log_writer.add_scalar(
                        k, tracked_means[k], global_step)


            if not args.soft_update:
                if global_step % args.update_target == 0:
                    agent.update_Q_t()
            else:
                agent.update_Q_t_soft()
            if global_step % args.save_interval == 0:
                torch.save(agent.Q.module.state_dict(), os.path.join(save_dir, "%s.pth"% global_step ))


       # torch.cuda.empty_cache() 
        results = {
               "path_length": agent.path_length,
               "reward": agent.reward,
               "success": int(agent.success),
               "eps_len": agent.eps_len,
               "SPL": int(agent.success) * agent.best_path_length\
                       / max(agent.path_length, agent.best_path_length)}
        train_scalars['all'].add_scalars(results)
        if agent.target not in train_scalars:
            train_scalars[agent.target] = ScalarMeanTracker()
        train_scalars[agent.target].add_scalars(results)

        ep_id += 1
        if ep_id % train_thin == 0:
            for cat in train_scalars:
                tracked_means = train_scalars[cat].pop_and_reset()
                for k in tracked_means:
                    log_writer.add_scalar(
                        "%s/%s" % (cat, k), tracked_means[k], ep_id)
        
        cckp = {
                "Q_t_state_dict": agent.Q_t.state_dict(),
                "Q_state_dict": agent.Q.state_dict(),
                "optimizer_state_dict": agent.optimizer.state_dict(),
                'ep_id': ep_id,
                "global_step": global_step,
                "save_dir": save_dir,
                "log_dir": log_dir,
                "train_scalars": train_scalars,
                "loss_q_reward": loss_q_reward,
                "current_position": agent.replay_buffer.position
                }
        torch.save(cckp, os.path.join(save_dir, 'checkpoint.pt'))

    pbar.close()
    log_writer.close()

if __name__ == "__main__":
    main()