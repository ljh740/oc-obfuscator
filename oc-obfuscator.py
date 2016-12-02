# -*- coding: utf-8 -*-
#   加固防dump-OC代码混淆器
#       by ch4r0n
import os
import re
import hashlib
import sys
import string,random
import argparse
import zipfile
from compiler.ast import flatten
import shutil
import time

str = '''
                       _      __                     _
  ___   ___       ___ | |__  / _|_   _ ___  ___ __ _| |_ ___  _ __
 / _ \ / __|____ / _ \| '_ \| |_| | | / __|/ __/ _` | __/ _ \| '__|
| (_) | (_|_____| (_) | |_) |  _| |_| \__ \ (_| (_| | || (_) | |
 \___/ \___|     \___/|_.__/|_|  \__,_|___/\___\__,_|\__\___/|_|

                                                    by ch4r0n
[1] Make sure your project is under the current directory.
[2] Input your project name.
[3] Input salt value, Only letters are allowed.
[4] If successful, an encrypted key-value is output, good luck..

-----------------------------------------------------------------
'''
#系统白名单 需要从文件读取
WHITE_LIST = []
#定义第三方SDK列表
SDK_LIST = ["XGPush","XGSetting","UMSocial","ShareSDK","MJRefresh","Masonry","AFNet","MJExtension","HUPhotoBrowser","MBProgressHUD","FMDB","WMPageController","BlocksKit","LPPopup","Pods","SDWebImage","BaiduMap","CocoaSecurity"]
#定义系统的主要函数列表 必须填.m
SYSTEM_LIST = ['main.m','Main.storyboard','LaunchScreen.xib','LaunchScreen.storyboard']
FILE_NAME = ['main','Main','LaunchScreen']
RES_KEY_PATH = 'reskeys.txt'
#需要加的前缀盐 (字母)



#读取白名单文件内容到列表中
def readTxtToList(r_path):
    tmplist = []
    txtpath = r_path
    fp = open(txtpath,'r')
    fstr = fp.read()
    tmplist = re.findall(r'\w+',fstr)
    return tmplist

#内容写入文件操作
def writeContextToFile(context,filepath):
    try:
        fwrite = open(filepath,'w')
        fwrite.write(context)
    except Exception,e:
        print str(e)
    fwrite.close()

#从文件读取内容操作
#返回值:文件内容串
def readContextFromFile(filepath):
    try:
        fread = open(filepath, 'r')
    except Exception, e:
        print str(e)
    tmpstr = fread.read()
    fread.close()
    return tmpstr


#过滤.m .h .pch文件
#在同级目录遍历,查找到所有的文件
#传入参数:项目绝对路径
def hmpchFilter(PATH):
    mergelist = []
    for list in os.walk(PATH):
     #过滤掉为空的列表
        if list[2] != []:
        #组合列表 拼凑出绝对路径
            for absfile in list[2]:
                mergelist.append(list[0] + '/' + absfile)
    filelist = []
    for mstr in mergelist:
    #过滤查找项目中.m和.h和.pch文件
        if mstr.endswith('.m') or mstr.endswith('.h') or mstr.endswith('.pch') or mstr.endswith('.xib') or mstr.endswith('.storyboard') or  mstr.endswith('.mm'):
            filelist.append(mstr)
    return filelist

#过滤第三方SDK文件 :
#参数 1.源列表 2.需要过滤的SDK列表
def listKeysFilter(list,unlist):
    result = []
    idxlist = len(list) - 1
    while idxlist >= 0:
        #定义找SDK 的标志位
        idxflag = 0
        for sdks in unlist:
            if sdks in list[idxlist]:
                idxflag = 1#包含了SDK flag 置1
                break
        if idxflag == 0:
            result.append(list[idxlist])
        idxlist = idxlist - 1
    return result


#获取第三方SDK文件 :
#参数 1.源列表 2.需要的SDK列表
def getSDKFileList(list,unlist):
    result = []
    idxlist = len(list) - 1
    while idxlist >= 0:
        for sdks in unlist:
            if sdks in list[idxlist]:
                result.append(list[idxlist])
                break
        idxlist = idxlist - 1
    return result

#获取到所有的类名,并且进行排重过滤 生成对应字典
#传入参数: 列表(已过滤)
#返回值:  字典
def keyDictCreate(list,SALT_KEY):
    all_cls_list = []
    #首先获取项目中所有的类名
    for str in list:
        result = re.findall(r'/(\w+|\w+\+\w+)\.', str)[-1]
        all_cls_list.append(result)
    #然后去重
    new_cls_list = {}.fromkeys(all_cls_list).keys()
    #生成对应的键值字典
    return secKeyCreate(new_cls_list,SALT_KEY)


#随机数密钥生成器
#返回值 : n位的随机数字符串(大小写)
def secKeyCreate(new_cls_list,SALT_KEY):
    sec_dic = {}
    for k in new_cls_list:
        #生成md5
        tmpv = hashlib.md5()
        tmpv.update(k + SALT_KEY)
        v = tmpv.hexdigest()
        v = '%s%s' % (SALT_KEY[0],v)
        sec_dic[k] = v
    return sec_dic

#将字典排列成有序的列表
#传入参数:无序字典
#返回值:有序的列表 包含所有的键 (+号优先)
def dictToOrderList(keydict):
    key_order_dic = {}
    #在有+号的字符串前插入1
    #没有+号的插入2
    for k,v in keydict.iteritems():
        if '+' in k:
            k = '1%s' % k
        else:
            k = '2%s' % k
        key_order_dic[k] = v
    #生成了有序的字典 但含有前字符1,2需要去除
    order_list = sorted(key_order_dic.iteritems())
    #去除字符 生成排序好的key
    key_order_list = []
    for i in order_list:
        key_order_list.append(i[0][1:])
    return key_order_list


#开始逐个进行替换操作
#参数1:列表(需要加密文件的绝对路径) 参数2:使用的加密字典
#返回值 : 成功与否标志
#替换操作
def replaceKeys(file_path_list, keydict):
    try:
        order_key = dictToOrderList(keydict)
    # 对文件名列表进行遍历
        for file_path in file_path_list:
            # 读取文件内容
            f_context = readContextFromFile(file_path)
            # 使用正则进行替换通篇文章
            for k in order_key:
                replace_reg = re.compile(r'\b(%s)\b' % k)
                f_context = replace_reg.sub(keydict[k], f_context)
                # f_context = f_context.replace(k, v)
            #写入到文件
            writeContextToFile(f_context, file_path)
        return True
    except Exception,e:
        print e
        return False


#替换属性名
#参数1:文件列表 参数2:加密的字典
def replaceAttributes(file_path_list,keydict):
    try:
    # 对文件名列表进行遍历
        for file_path in file_path_list:
            # 读取文件内容
            f_context = readContextFromFile(file_path)
            # 使用正则进行替换通篇文章
            for k, v in keydict.iteritems():
                replace_reg = re.compile(r'\b(%s)\b' % k)
                f_context = replace_reg.sub(v, f_context)
                # f_context = f_context.replace(k,v)
                #写入信息到文件中
                writeContextToFile(f_context, file_path)
        return True
    except Exception, e:
        print e
        return False



#提取所有方法,存放在一个列表里
#参数list: 已过滤的文件列表
#return 列表:所有方法
def getAllmethod(file_path_list):
    #用于存放方法
    method_list = []
    method_name_list = []
    #遍历所有文件名
    for file_path in file_path_list:
        #读取文件内容
        m_file = readContextFromFile(file_path)
        result = re.findall(r'(?:^|\n)([\-|\+].*)', m_file)
        method_list.append(result)
    method_name_list = flatten(method_list)
    return method_name_list

#提取所有方法,存放在一个列表里
#参数list: 已过滤的文件列表
#return 字典:所有需要混淆的方法名和对应的MD5
def getAllmethodName(method_list,SALT_KEY):
    #用于存放方法名
    method_name_list = []
    #遍历存放方法的列表
    for method_name in method_list:
        #读取文件内容
        result = re.findall(r'\w+', method_name)
        method_name_list.append(result)
    #提取第一个方法名
    first_name = []
    for f_name in method_name_list:
        result = f_name[1]
        first_name.append(result)
    #去重
    first_name_qc = []
    first_name_qc = {}.fromkeys(first_name).keys()

    # 生成20位的随机数字母用作密钥

     # 合并密钥和类名为一个字典
    return secKeyCreate(first_name_qc,SALT_KEY)

#添加属性名到白名单
#参数1:原白名单列表 参数2:SDK密码字典
def addSDKToWhiteList(list,dict):
    tmplist = list
    for k,v in dict.iteritems():
        tmplist.append(k)
    return tmplist

#获取所有的属性名加密到字典中
#参数1:传入的文件列表 参数2:白名单过滤
#返回值:属性加密后的字典
def keyAttriCreate(file_path_list,white_list,SALT_KEY):
    all_attri_list = []
    # 对文件名列表进行遍历
    for file_path in file_path_list:
        # 读取文件内容
        f_context = readContextFromFile(file_path)
        # 使用正则通篇替换 首先读取到属性的每一行 @property
        # 提取出@property 的特征字符串
        property_list = re.findall(r"\@property.*;", f_context)
        # 提取出property的最后一个关键字 即属性名
        for longstr in property_list:
            attri_str = re.findall(r'(\w+)', longstr)[-1]
            all_attri_list.append(attri_str)
    # 然后去重
    new_attri_list = {}.fromkeys(all_attri_list).keys()
    # 白名单过滤
    filtered_attri_list = []
    for attr in new_attri_list:
        white_flag = 0
        for wstr in white_list:
            if wstr == attr:
                white_flag = 1;
        #如果遍历完白名单仍然没找到这个名字 说明他不在白名单中
        if white_flag == 0:
            filtered_attri_list.append(attr)
    return secKeyCreate(filtered_attri_list,SALT_KEY)


#进行修改文件名操作
#参数1.文件路径 2.加密字典
def doModifiFileName(file_path_list,keydict,PATH):
    dict_file = {}
    #重新拼接文件名
    for filename in file_path_list:
        # 获取路径 /sdlkj/dkfjlkd/
        class_path = re.findall(r'.*/', filename)
        # 获取后缀 .m
        suffix = re.findall(r'(\.\w+)', filename)[-1]
        # 拼接新的路径
        filter_str = re.findall(r'/(\w+|\w+\+\w+)\.', filename)[-1]
        if keydict.has_key(filter_str):
            new_path = ''.join(class_path) + keydict[filter_str] + ''.join(suffix)
        else:
            new_path = filename
        #重命名文件
        os.rename(filename,new_path)
        #将加密的文件名和原文件名放到字典中
        old_path_str = filename.split("/")[-1]
        new_path_str = new_path.split("/")[-1]
        dict_file[old_path_str] = new_path_str

    #字典处理 将+号转换成\+
    dict_file = spcSymbolFilter(dict_file,'+')
    dict_file = spcSymbolFilter(dict_file,'.')

    #保留关键字替换path .pbxproj(确保工程重新组织)
    #找到xcodeproj文件
    for filename in os.walk(PATH):

        for file in filename[2]:
            if "pbxproj" in file:
                pbx_path = filename[0] + "/" + "project.pbxproj"
                # 打开文件
                xpb_context = readContextFromFile(pbx_path)
                for k, v in dict_file.iteritems():
                    # 找到需要替换的位置
                    # 进行替换操作
                    replace_reg = re.compile(r'\b(%s)\b' % k)
                    xpb_context = replace_reg.sub(v, xpb_context)
                # 写入文件
                writeContextToFile(xpb_context, pbx_path)

#过滤字典中的系统关键字
#参数1:需要过滤的字典 2:白名单
def dictKeywordFilter(dict,list):
    tmp = {}
    #未找到相同的
    flag = 0
    for k,v in dict.iteritems():
        flag = 0
        for li in list:
            if li == k:
                flag = 1
        if flag == 0:
            tmp[k] = v
    return tmp

#过滤所有字典,添加转义字符到特殊符号
#参数1:字典 2:需要找的转义符号
def spcSymbolFilter(dict,str):
    tmp = {}
    for k,v in dict.iteritems():
        if str in k:
            k = k.replace(str,'\%s' % str)
        tmp[k] = v
    return tmp

#对属性名添加下划线 组成self
def addUnderLineAttrKey(dict):
    tmpdic = {}
    for k,v in dict.iteritems():
        tmpdic[k] = v
        tk = "_" + k
        tv = "_" + v
        tmpdic[tk] = tv
    return tmpdic

#添加属性名到白名单
#参数1:原白名单列表 参数2:属性密码字典
def addAtttriToWhiteList(list,dict):
    tmplist = list
    for k,v in dict.iteritems():
        tmplist.append(k)
        set_k = 'set%s%s' % (k[0].upper(),k[1:])
        tmplist.append(set_k)
    return tmplist

#在字典中过滤init方法
def initMethodFilter(dict):
    tmpDict = {}
    for k,v in dict.iteritems():
        if 'init' not in k:
            tmpDict[k] = v
    return tmpDict

#重命名其他的资源文件 排查
def renameOtherResource(dict,PATH):
    try:
        mergelist = []
        dict_file = {}
        for list in os.walk(PATH):
            if list[2] != []:
            # 组合列表 拼凑出绝对路径
                for absfile in list[2]:
                    mergelist.append(list[0] + '/' + absfile)
    #重新拼接文件名
        for filename in mergelist:
        # 获取后缀 .m
            suffix = re.findall(r'\.[^.\\/:*?"<>|\r\n]+$', filename)
            if suffix == []:
                continue
            class_path = re.findall(r'.*/', filename)
        # 拼接新的路径
            filter_str = re.findall(r'/(\w+|\w+\+\w+)\.', filename)
            if filter_str != []:
                class_str = filter_str[-1]
                if dict.has_key(class_str):
                    new_path = ''.join(class_path) + dict[class_str] + ''.join(suffix)
                #重命名文件
                    os.rename(filename,new_path)
                # 将加密的文件名和原文件名放到字典中
                    old_path_str = filename.split("/")[-1]
                    new_path_str = new_path.split("/")[-1]
                    dict_file[old_path_str] = new_path_str
                # 保留关键字替换path .pbxproj(确保工程重新组织)
        # 找到xcodeproj文件
            for filename in os.walk(PATH):
                for file in filename[2]:
                    if "pbxproj" in file:
                        pbx_path = filename[0] + "/" + "project.pbxproj"
                    # 打开文件
                        xpb_context = readContextFromFile(pbx_path)
                        for k, v in dict_file.iteritems():
                        # 找到需要替换的位置
                        # 进行替换操作
                            replace_reg = re.compile(r'\b(%s)\b' % k)
                            xpb_context = replace_reg.sub(v, xpb_context)
                    # 写入文件
                        writeContextToFile(xpb_context, pbx_path)
    except Exception, e:
        print e
        return False

#获取所有需要加密的文件
#返回值: 元组(需要加密的文件列表,工程下所有的.h.m.pch文件)
def getNeedEncryptFileList(PATH):
    # step 1:获取到工程下的所有.h .m .pch
    hmp_list = hmpchFilter(PATH)
    # step 1.1:获取到需要进行加密的文件的绝对路径 (过滤SDK)
    need_encrypt_files_list = listKeysFilter(hmp_list, SDK_LIST)
    return (need_encrypt_files_list,hmp_list)

#获取所有的文件
#返回值 1:类名字典
#返回值 2:类名字典(带下划线)
#返回值 3:方法名字典
#返回值 4:属性名字典
def getAllKeys(need_encrypt_files_list,hmp_list,SALT_KEY,WHITE_LIST):

    # print 'test,',WHITE_LIST
    cls_key_dic = keyDictCreate(need_encrypt_files_list,SALT_KEY)
    cls_key_dic = dictKeywordFilter(cls_key_dic, WHITE_LIST)
    # 包含\+的字典
    cls_key_dic_slash = spcSymbolFilter(cls_key_dic, '+')

    # 生成属性名字典 过滤了白名单
    attri_key_dic = keyAttriCreate(need_encrypt_files_list, WHITE_LIST,SALT_KEY)
    attri_key_dic_underline = addUnderLineAttrKey(attri_key_dic)

    #生产方法名字典
    #添加属性名get、set到白名单
    TMP_LIST = addAtttriToWhiteList(WHITE_LIST,attri_key_dic_underline)
    # 获取第三方SDK文件路径
    SDK_filter_list = getSDKFileList(hmp_list, SDK_LIST)
    # 获取第三方SDK方法名(字典)
    SDK_method_list = getAllmethod(SDK_filter_list)
    SDK_method_name_list = getAllmethodName(SDK_method_list,SALT_KEY)
    # 第三方SDK方法加入白名单
    TMP_LIST2 = addSDKToWhiteList(TMP_LIST, SDK_method_name_list)
    list_m = getAllmethod(need_encrypt_files_list)
    method_key_dic = getAllmethodName(list_m,SALT_KEY)
    method_key_dic = dictKeywordFilter(method_key_dic, TMP_LIST2)
    # 过滤init前缀方法
    method_key_dic = initMethodFilter(method_key_dic)

    return (cls_key_dic,
            cls_key_dic_slash,
            method_key_dic,
            attri_key_dic)

#开始混淆
#参数 1:需要加密的文件列表
#参数 2:加密的类字典(带有转义字符)
#参数 3:加密的方法字典
#参数 4:加密的属性字典
def startWorks(need_encrypt_files_list,class_key_dic_slash,method_key_dic,attributes_key_dic):
    #加密类名
    replaceKeys(need_encrypt_files_list,class_key_dic_slash)
    #加密方法名
    replaceKeys(need_encrypt_files_list,method_key_dic)
    #加密属性名(砍掉) 避免与通信接口不一致导致的各种问题
    #大神有更好的方法请联系我 email:xingrenchan@gmail.com
    # replaceAttributes(need_encrypt_files_list,attributes_key_dic)

#文件重命名操作
#参数 1:需要加密的文件名
#参数 2:类名字典
#参数 3:类名字典(带下划线)
#参数 3:方法字典
#参数 4:属性名字典
def renameFile(PATH,need_encrypt_files_list,cls_key_dic,cls_key_dic_slash,method_key_dic,attri_key_dic):
    #需要重命名的文件
    need_rename_file_list = listKeysFilter(need_encrypt_files_list, SYSTEM_LIST)
    doModifiFileName(need_rename_file_list, cls_key_dic,PATH)
    # 所有加密字典进行合并
    dict_tmp = dict(cls_key_dic_slash,**method_key_dic)
    all_keys_dict = dictKeywordFilter(dict_tmp,FILE_NAME)
    #再命名其他资源文件
    renameOtherResource(all_keys_dict,PATH)
    return all_keys_dict


def travelTree(currentPath, count):

    if not os.path.exists(currentPath):
        return
    if os.path.isfile(currentPath):
        fileName = os.path.basename(currentPath)
        print '\t' * count + '├── ' + fileName
    elif os.path.isdir(currentPath):
        print '\t' * count + '├── ' + currentPath
        pathList = os.listdir(currentPath)
        for eachPath in pathList:
            travelTree(currentPath + '/' + eachPath, count + 1)

def outPutLog(all_keys):
    try:
    #在该目录下创建log
        ABSPATH = os.path.dirname(os.path.abspath(sys.argv[0])) + "/"
        filestr = ABSPATH+'seclog.txt'
        fopen = open(filestr,'w+')
        fopen.write(''' ____ ____ ____ ____ ____ ____ ____ ____ ____
||V |||a |||l |||u |||e |||- |||K |||e |||y ||
||__|||__|||__|||__|||__|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/__\|/__\|/__\|/__\|\n\n''')
        ISOTIMEFORMAT = '%Y-%m-%d %X'
        timestamp = time.strftime(ISOTIMEFORMAT, time.localtime())
        fopen.writelines('time:'+timestamp+'\n')

        for k,v in all_keys.iteritems():
            tmpstr = '%s\t\t%s\n' % (v,k)
            fopen.writelines(tmpstr)
        fopen.close()
        print "LogPath:",filestr
        return True
    except Exception,e:
        print e
        return False


def inputArgs():
    WHITE_LIST = readTxtToList(RES_KEY_PATH)
    ABSPATH = os.path.abspath(sys.argv[0])
    ABSPATH = os.path.dirname(ABSPATH) + "/"
    projectFile = ABSPATH + raw_input("->ProjectName:")
    if os.path.exists(projectFile) == True:
        travelTree(projectFile,1)
        print "Project Path:",projectFile,'\n'
    else:
        print "Are you sure the file is exists?"
        exit()

    SALT = raw_input("SaltKey:")
    if SALT.isalpha() == False:
        print "can not include (1-9) or (@!#%^...)"
        exit()

    need_encrypt_file_tuple = getNeedEncryptFileList(projectFile)
    all_keys_tuple = getAllKeys(need_encrypt_file_tuple[0], need_encrypt_file_tuple[1], SALT, WHITE_LIST)
    startWorks(need_encrypt_file_tuple[0], all_keys_tuple[1], all_keys_tuple[2], all_keys_tuple[3])
    allkeys = renameFile(projectFile, need_encrypt_file_tuple[0], all_keys_tuple[0], all_keys_tuple[1],
                         all_keys_tuple[2], all_keys_tuple[3])
    outPutLog(allkeys)
    print 'success!'



if __name__ == '__main__':
    # parseArgs()
    print str
    inputArgs()



