import json
import os.path
import pathlib
import re
import shutil
import subprocess

import requests
from bs4 import BeautifulSoup

from compress import compress_dir_with_bandizip, decompress_dir_with_bandizip
from download import download_file
from log import color, logger
from upload_lanzouyun import Uploader
from util import change_console_window_mode_async, make_sure_dir_exists, pause, remove_directory, remove_file

TEMP_DIR = "utils/chrome_temporary_dir"
SRC_DIR = os.path.realpath(".")

CHROME_DRIVER_EXE = "chromedriver.exe"


def download_latest_chrome_driver():
    latest_version = get_latest_chrome_driver_version()
    windows_zip = "chromedriver_win32.zip"

    latest_download_url = f"https://chromedriver.storage.googleapis.com/{latest_version}/{windows_zip}"

    logger.info(f"最新版本的chrome driver为: {latest_version}，下载地址为 {latest_download_url}")

    zip_file = download_file(latest_download_url, ".")
    decompress_dir_with_bandizip(zip_file, dir_src_path=SRC_DIR)

    # 移除临时文件
    remove_file(zip_file)

    # 重命名
    major_version = parse_major_version(latest_version)
    chrome_driver = f"chromedriver_{major_version}.exe"
    os.rename(CHROME_DRIVER_EXE, chrome_driver)
    logger.info(f"重命名为 {chrome_driver}")

    version_info = subprocess.check_output([os.path.realpath(chrome_driver), "--version"]).decode("utf-8")
    logger.info(color("bold_green") + f"chrome获取完毕，chrome driver版本为 {version_info}")


def get_latest_chrome_driver_version() -> str:
    res = requests.get("https://chromedriver.storage.googleapis.com/LATEST_RELEASE")

    return res.text


def parse_major_version(latest_version: str) -> int:
    return int(latest_version.split(".")[0])


def get_latest_major_version() -> int:
    return parse_major_version(get_latest_chrome_driver_version())


def create_portable_chrome():
    latest_dir = get_latest_installed_chrome_version_directory()
    major_version = parse_major_version(os.path.basename(latest_dir))

    latest_installer = os.path.join(latest_dir, "Installer", "chrome.7z")

    logger.info(f"复制 {latest_installer} 到 当前目录中 {os.getcwd()}")
    shutil.copy2(latest_installer, ".")

    logger.info("解压缩后重新压缩，减小大小")
    temp_zip = os.path.basename(latest_installer)
    decompress_dir_with_bandizip(temp_zip, dir_src_path=SRC_DIR)

    decompressed_dir = "Chrome-bin"
    new_zip_name = f"chrome_portable_{major_version}.7z"
    logger.info(color("bold_yellow") + f"开始重新压缩打包为 {new_zip_name}，大概需要一到两分钟，请耐心等候~ ")
    compress_dir_with_bandizip(decompressed_dir, new_zip_name, dir_src_path=SRC_DIR, extra_options=["-storeroot:no"])

    logger.info("移除中间文件")
    remove_file(temp_zip)
    remove_directory(decompressed_dir)

    logger.info(color("bold_yellow") + f"便携版已制作完毕: {new_zip_name}")


def get_latest_installed_chrome_version_directory() -> str:
    chrome_dir = os.path.expandvars("%PROGRAMFILES%/Google/Chrome/Application")

    for entry in pathlib.Path(chrome_dir).glob("*"):
        if not entry.is_dir():
            continue

        if re.match(r"\d+\.\d+\.\d+\.\d+", entry.name):
            return str(entry)

    raise FileNotFoundError("未找到最新安装的chrome目录")


def download_chrome_installer():
    download_page = requests.get("https://www.iplaysoft.com/tools/chrome/").text

    soup = BeautifulSoup(download_page, "html.parser")

    latest_version_soup = soup.find("div", class_="ui segment")

    download_url = latest_version_soup.find("a", class_="ui positive button").get("href")
    latest_version = latest_version_soup.find("code").text[1:]

    logger.info(f"最新版本的下载链接为: {download_url}")
    download_file(download_url, ".", f"Chrome_{latest_version}_普通安装包_非便携版.exe")


def update_qq_login_version():
    major_version = get_latest_major_version()

    qq_login_file = os.path.join(SRC_DIR, "qq_login.py")

    replace_text_in_file(qq_login_file, r"chrome_major_version = (\d+)", f"chrome_major_version = {major_version}")
    logger.info(f"已将 {qq_login_file} 中的 chrome_major_version 修改为 {major_version}")


def replace_text_in_file(filepath: str, pattern: str, repl: str):
    original_contents = open(filepath, encoding="utf-8").read()
    updated_contents = re.sub(pattern, repl, original_contents)

    open(filepath, "w", encoding="utf-8").write(updated_contents)


def update_linux_version():
    latest_version = get_latest_chrome_driver_version()

    ubuntu_file = os.path.join(SRC_DIR, "_ubuntu_download_chrome_and_driver.sh")
    centos_file = os.path.join(SRC_DIR, "_centos_download_and_install_chrome_and_driver.sh")

    # 100.0.4896.75
    re_version = r"(\d+)\.(\d+)\.(\d+)\.(\d+)"

    replace_text_in_file(ubuntu_file, re_version, str(latest_version))
    replace_text_in_file(centos_file, re_version, str(latest_version))
    logger.info(f"已将linux更新脚本中的版本替换为 {latest_version}")


def upload_all_to_lanzou():
    uploader = Uploader()

    with open(os.path.join(SRC_DIR, "upload_cookie.json")) as fp:
        cookie = json.load(fp)
    uploader.login(cookie)

    if uploader.login_ok:
        wanted_file_regex_list = [
            r"chromedriver_(\d+).exe",
            r"chrome_portable_(\d+).7z",
            r"Chrome_(\d+)\.(\d+)\.(\d+)\.(\d+)_普通安装包_非便携版.exe",
        ]

        files = list(pathlib.Path(".").glob("*"))
        for wanted_file_regex in wanted_file_regex_list:
            for file in files:
                if not re.match(wanted_file_regex, file.name):
                    continue

                logger.info(f"开始上传 {file.name}")
                uploader.upload_to_lanzouyun(str(file), uploader.folder_djc_helper_tools, delete_history_file=True)
    else:
        logger.error(f"登录失败，请手动上传 {TEMP_DIR} 中的文件到蓝奏云")


def update_latest_chrome():
    # 最大化窗口
    change_console_window_mode_async(disable_min_console=True)

    # 重置临时目录
    remove_directory(TEMP_DIR)
    make_sure_dir_exists(TEMP_DIR)

    logger.info(f"临时切换到 {TEMP_DIR}，方便后续操作")
    os.chdir(TEMP_DIR)

    # 下载chrome driver
    download_latest_chrome_driver()

    # 制作chrome便携版
    create_portable_chrome()

    # 下载chrome安装包
    download_chrome_installer()

    # 修改 qq_login.py 中的版本号为新的主版本号
    update_qq_login_version()

    # 更新linux版的路径
    update_linux_version()

    # 上传到蓝奏云
    upload_all_to_lanzou()

    # 提示确认代码修改是否无误
    logger.info(color("bold_green") + "请检查一遍代码，然后执行一遍 qq_login.py，以确认新的chrome制作无误，然后点击任意键提交git即可完成流程")
    pause()

    # git commit 相关代码
    os.chdir(SRC_DIR)
    latest_version = get_latest_chrome_driver_version()
    subprocess.call(
        [
            "git",
            "add",
            "qq_login.py",
            "_centos_download_and_install_chrome_and_driver.sh",
            "_ubuntu_download_chrome_and_driver.sh",
        ]
    )
    subprocess.call(["git", "commit", "-m", f"feat: 升级chrome版本到{latest_version}"])

    logger.info(f"更新完毕，清理临时目录 {TEMP_DIR}")
    remove_directory(TEMP_DIR)

    # 最后暂停下，方便确认结果
    pause()


if __name__ == "__main__":
    update_latest_chrome()
