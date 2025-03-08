from lib import stockbrokers, singleton, errors, util, issues, defs
from datetime import datetime
from dateutil.relativedelta import relativedelta

import time
import argparse
import sys
import numpy as np
import pandas as pd
import shutil
import os

    #0. 기본 설정
APP_KEY = 'PS98hMu5jmnQt9SnXAOhD2cs91mjUc607PQJ'
APP_SECRET_KEY = 'sJVk0BpvmUCD1cmM8OPAtyZPkqoQo5w2' 

sec = stockbrokers.LSSec("", APP_KEY, APP_SECRET_KEY, True)


parser = argparse.ArgumentParser()

DEF_DAY = "D"
parser.add_argument("--day", help="Day(D)/Night(N)", default=DEF_DAY)

DEF_BASE_DT = datetime.now().strftime("%Y%m%d") 
parser.add_argument("--base_dt", help="YYYYMMDD", default=DEF_BASE_DT)

DEF_DIR = "./test2"
parser.add_argument("--data_dir", help="data download directory", default=DEF_DIR)

args = parser.parse_args()

#base_dt
base_dt = args.base_dt

#다운로드 폴더 및 파일 초기화
dn_data = f"{args.data_dir}/{base_dt}"
if not os.path.exists(dn_data):
    os.makedirs(dn_data)
    
#가격정보 파일 삭제
fn_price = f"{dn_data}/price.csv"
if os.path.exists(fn_price):
    os.remove(fn_price)

#tick 폴더 생성
dn_tick = f"{dn_data}/tick"
if os.path.exists(dn_tick):
    shutil.rmtree(dn_tick)    
os.makedirs(dn_tick)
    
DAY_MARKET = True
    
#2. 만기년월 BASE_YM 만들기
base_ym = base_dt[0:6]

#2.1 BASE_YM에 해당하는 KOSPI200 MINI 시세정보 얻기
isu_cd_bcmk = issues.get_fo_isu_cd(issues.ISIN_FUTURE, issues.ISIN_FO_KOSPI200_MN, base_ym) 

#2.2 KOSPI200 MINI 시세 정보 얻는 것을 실패하면, BASE_YM을 다음 월로 변경
chart_bcmk = sec.get_chart(isu_cd_bcmk, base_dt)
if chart_bcmk is None:
    base_ym = datetime.strptime(base_ym, "%Y%m") + relativedelta(months=1)
    base_ym = base_ym.strftime("%Y%m")

#3. 옵션행사가 범위 설정(기준일자 종가에서 +/- 150 tick)
#3.1 기준가격 설정 = 기준가격 기준일자 벤치마크 종목(KOSPI200 MINI)의 종가 얻기
isu_cd_bcmk = issues.get_fo_isu_cd(issues.ISIN_FUTURE, issues.ISIN_FO_KOSPI200_MN, base_ym) 
chart_bcmk = sec.get_chart(isu_cd_bcmk, base_dt)
base_pr = chart_bcmk["close"]

#3.2 옵션행사가 범위 = 기준가격 +/- 150tick
OPT_STRK_INTVL = 2.5
N_OPT_STRK = 150
opt_base_strk = round(base_pr / OPT_STRK_INTVL) * OPT_STRK_INTVL
opt_min_strk = max(OPT_STRK_INTVL, opt_base_strk - OPT_STRK_INTVL * N_OPT_STRK)
opt_max_strk = opt_base_strk + OPT_STRK_INTVL * N_OPT_STRK
opt_strks = np.arange(opt_min_strk, opt_max_strk, OPT_STRK_INTVL)

#4. 선물/옵션 코드 만들기
isu_cds = []
for add_m in range(0, 4):
    m_ym = datetime.strptime(base_ym, "%Y%m") + relativedelta(months=add_m)
    m_ym = m_ym.strftime("%Y%m")

    #4.1 KOSPI200코드 생성 
    if m_ym[4:6] in ["03", "06", "09", "12"]:
        isu_cd = issues.get_fo_isu_cd(issues.ISIN_FUTURE, issues.ISIN_FO_KOSPI200, m_ym)
        isu_cds.append(isu_cd)
        
    #4.2 KOSPI200 MINI 코드 생성    
    isu_cd = issues.get_fo_isu_cd(issues.ISIN_FUTURE, issues.ISIN_FO_KOSPI200_MN, m_ym) 
    isu_cds.append(isu_cd)
        
    #4.3 OPTION 코드 생성
    for opt_strk in opt_strks:
        opt_strk = f"{int(opt_strk):03d}"
        
        #KOSPI200 CALL OPTION
        isu_cd = issues.get_fo_isu_cd(issues.ISIN_FTROPT_C, issues.ISIN_FO_KOSPI200, m_ym, opt_strk)
        isu_cds.append(isu_cd)
        
        #KOSPI200 PUT OPTION
        isu_cd = issues.get_fo_isu_cd(issues.ISIN_FTROPT_P, issues.ISIN_FO_KOSPI200, m_ym, opt_strk)
        isu_cds.append(isu_cd)
        
        #KOSPI200 MINI CALL OPTION
        isu_cd = issues.get_fo_isu_cd(issues.ISIN_FTROPT_C, issues.ISIN_FO_KOSPI200_MN, m_ym, opt_strk)
        isu_cds.append(isu_cd)
        
        #KOSPI200 MINI PUT OPTION
        isu_cd = issues.get_fo_isu_cd(issues.ISIN_FTROPT_P, issues.ISIN_FO_KOSPI200_MN, m_ym, opt_strk) 
        isu_cds.append(isu_cd)

#5 선물/옵션 가격 정보 받기
prices = []
start_time = 0

for isu_cd in isu_cds:
    elapsed_time = time.time() - start_time  # 경과 시간 계산    print(isu_cd)
    if elapsed_time < 1:
        time.sleep(1-elapsed_time)
    start_time = time.time()  # 시작 시간 기록
    print(isu_cd)
    chart = sec.get_chart(isu_cd, base_dt)
    if chart is None:
        continue
    prices.append(chart)
    
    tick = sec.get_tick_day(isu_cd, base_dt)
    if tick is None:
        continue
    
    #tick 정보 저장
    tick["data"].to_csv(f"{dn_tick}/tick_{isu_cd}.csv", index=False)
    
#가격 정보 저장
price = pd.DataFrame(prices)
price.to_csv(fn_price, index=False) 

    