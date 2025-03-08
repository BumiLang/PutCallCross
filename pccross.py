import pandas as pd
import re
import numpy as np
import scipy.optimize as spo
import os
import glob

from datetime import datetime, timedelta

OPEN_TIME = '00:00:00'
CLOSE_TIME = '24:00:00'

def get_opt_price_f(f_path):
    opt = pd.read_csv(f_path, encoding = 'CP949');
    opt = opt.rename(columns = {'일자' : 'DATE', '시간' : 'TIME', '선물가격' : 'FUT'});
    
    if len(opt) == 0:
        return None
    
    if re.match(r'^\d{4}-\d{2}-\d{2}$', opt['DATE'][0]):
        opt['DATE'] = opt['DATE'].str.replace('-', '')
        
    if opt['TIME'].dtype == 'float64' :
        opt['TIME'] = pd.to_datetime(opt['TIME'], unit = 'd').apply(lambda x : (x + timedelta(seconds=0.5)).strftime("%H:%M:%S"))
        
    opt = pd.melt(opt, id_vars=['DATE', 'TIME'], var_name= 'INST', value_name='PR');
    fut = opt.loc[opt['INST'] == 'FUT'][['DATE', 'TIME', 'PR']];
    
    opt = opt.loc[(opt['INST'] != 'FUT') & (opt['INST'] < '900')];
    opt = opt.rename(columns = {'INST' : 'STRK'}); 
    opt = opt.astype({'STRK' : 'float'}); 
    
    opt = opt.reset_index(drop = True).sort_values(['DATE', 'TIME', 'STRK']);
    fut = fut.reset_index(drop = True).sort_values(['DATE', 'TIME']);
    
    return opt, fut;


def get_opt_price(yrmo, type, dir):
    dir_ym = dir + '/' + str(yrmo)
    
    ohlc = '_C'
    if type.lower() == 'o' :
        ohlc = '_O'
    elif type.lower() == 'h' :
        ohlc = '_H'
    elif type.lower() == 'l' :
        ohlc = '_L'
        
    copt = pd.DataFrame()
    popt = pd.DataFrame()
    fut = pd.DataFrame()
    
    date = set([fn_i[0:8] for fn_i in os.listdir(dir_ym)])
    for date_i in date:
        
        #call option 가격 가져오기
        f_call_i = dir_ym + '/' + date_i + '_Call' + ohlc + '.csv';
        [copt_i, fut_c_i] = get_opt_price_f(f_call_i);
        
        #put option 가격 가져오기
        f_put_i = dir_ym + '/' + date_i + '_Put' + ohlc + '.csv';
        [popt_i, fut_p_i] = get_opt_price_f(f_put_i);        
            
        #선물 가격 재생성
        fut_i = pd.merge(fut_c_i, fut_p_i, how = 'outer', on = ['DATE', 'TIME'], suffixes = ('_C', '_P'));
        fut_i['PR'] = fut_i['PR_C'].fillna(fut_i['PR_P']);
        fut_i.drop(columns = ['PR_C', 'PR_P'], inplace = True);
        
        copt = pd.concat([copt, copt_i])
        popt = pd.concat([popt, popt_i])
        fut = pd.concat([fut, fut_i])
    
    copt = copt.reset_index(drop = True).sort_values(['DATE', 'TIME', 'STRK']);
    popt = popt.reset_index(drop = True).sort_values(['DATE', 'TIME', 'STRK']);
    fut = fut.reset_index(drop = True).sort_values(['DATE', 'TIME']);
    
    return copt, popt, fut;

def get_opt_atm(yrmo, d_dir, eqvl_srch_rng = 5):
    
    #시가
    [copt_o, popt_o, fut_o] = get_opt_price(yrmo = yrmo, type = 'o', dir = d_dir);
    
    #고가
    [copt_h, popt_h, fut_h] = get_opt_price(yrmo = yrmo, type = 'h', dir = d_dir);
    
    #저가
    [copt_l, popt_l, fut_l] = get_opt_price(yrmo = yrmo, type = 'l', dir = d_dir);
    
    #종가
    [copt_c, popt_c, fut_c] = get_opt_price(yrmo = yrmo, type = 'c', dir = d_dir);
   
    #선물/옵션 데이터 합치기
    fut = pd.merge(fut_c, fut_o, how = 'left', on =['DATE', 'TIME'], suffixes=('', '_O'));
    fut = pd.merge(fut, fut_h, how = 'left', on =['DATE', 'TIME'], suffixes=('', '_H'));
    fut = pd.merge(fut, fut_l, how = 'left', on =['DATE', 'TIME'], suffixes=('', '_L'));
    
    fut = fut.rename(columns = {'PR' : 'FUT', 
                                'PR_O' : 'FUT_O', 
                                'PR_H' : 'FUT_H', 
                                'PR_L' : 'FUT_L', });
    
    copt = pd.merge(copt_c, copt_o, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_O'));
    copt = pd.merge(copt, copt_h, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_H'));
    copt = pd.merge(copt, copt_l, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_L'));
    
    popt = pd.merge(popt_c, popt_o, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_O'));
    popt = pd.merge(popt, popt_h, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_H'));
    popt = pd.merge(popt, popt_l, how = 'left', on =['DATE', 'TIME', 'STRK'], suffixes=('', '_L'));
    
    copt_tmp = copt.rename(columns = {'PR' : 'C_PR', 
                                      'PR_O' : 'C_PR_O', 
                                      'PR_H' : 'C_PR_H', 
                                      'PR_L' : 'C_PR_L', });

    popt_tmp = popt.rename(columns = {'PR' : 'P_PR', 
                                      'PR_O' : 'P_PR_O', 
                                      'PR_H' : 'P_PR_H', 
                                      'PR_L' : 'P_PR_L', });

    opt = pd.merge(copt_tmp, popt_tmp, how = 'inner', on = ['DATE', 'TIME', 'STRK']);
    opt = pd.merge(fut, opt, how = 'left', on = ['DATE', 'TIME'])

    #옵션 우세 찾기
    opt.loc[opt['C_PR'] > opt['P_PR'], 'OPT_DMNT'] = 'C';
    opt.loc[opt['C_PR'] < opt['P_PR'], 'OPT_DMNT'] = 'P';

    opt = opt.sort_values(by = ['DATE', 'STRK', 'TIME'], ascending=[True, True, True]);
    opt['OPT_DMNT'] = opt.groupby(['DATE', 'STRK'])['OPT_DMNT'].ffill();
    opt['OPT_DMNT_PRV'] = opt.groupby(['DATE', 'STRK'])['OPT_DMNT'].shift(1);

    opt_1st_idx = opt.groupby(['DATE', 'STRK']).head(1).index;
    opt.loc[opt_1st_idx, 'OPT_DMNT_PRV'] = np.where(opt.loc[opt_1st_idx, 'C_PR_O'] > opt.loc[opt_1st_idx, 'P_PR_O'], 'C', 
                                          np.where(opt.loc[opt_1st_idx, 'C_PR_O'] < opt.loc[opt_1st_idx, 'P_PR_O'], 'P', 'E'))

    #만기 및 만기까지 남은 날
    opt['MATURITY'] = opt['DATE'].max();
    opt['D-Days'] = (pd.to_datetime(opt['MATURITY'], format = '%Y%m%d') - pd.to_datetime(opt['DATE'], format = '%Y%m%d')).dt.days;
    opt['BizD-Days'] = opt['DATE'].rank(ascending = [True, False], method = 'dense') - 1;

    opt = opt[['DATE', 'MATURITY', 'D-Days', 'BizD-Days', 'TIME', 
               'FUT', 'FUT_O', 'FUT_H', 'FUT_L', 
               'STRK', 'C_PR', 'C_PR_O', 'C_PR_H', 'C_PR_L', 'P_PR', 'P_PR_O', 'P_PR_H', 'P_PR_L', 'OPT_DMNT_PRV', 'OPT_DMNT']];
    
    opt['EQVL_SUM'] = opt['C_PR'] + opt['P_PR'];

    opt['DIST'] = abs(opt['FUT'] - opt['STRK']);

    #atm 찾기
    atm_srch_rng = 5
    opt_srch = opt[((opt['FUT'] - atm_srch_rng <= opt['STRK']) & (opt['STRK'] <= opt['FUT'] + atm_srch_rng)) & \
                    ((opt['FUT'] - atm_srch_rng <= opt['STRK']) & (opt['STRK'] <= opt['FUT'] + atm_srch_rng))].copy();
    opt_srch = opt_srch.sort_values(['DATE', 'TIME', 'EQVL_SUM', 'DIST', 'STRK'], ascending=[True, True, True, True, False])
    opt_srch['RNK'] = opt_srch.groupby(['DATE','TIME']).cumcount() + 1;
                                
    opt_atm = opt_srch[opt_srch['RNK'] == 1].drop(columns = ['RNK', 'DIST']);

    opt_atm.insert(0, 'YRMO', yrmo)
    copt.insert(0, 'YRMO', yrmo)
    popt.insert(0, 'YRMO', yrmo)
    fut.insert(0, 'YRMO', yrmo)
    
    opt_atm.reset_index(drop=True, inplace=True)
    copt.reset_index(drop=True, inplace=True)
    popt.reset_index(drop=True, inplace=True)
    fut.reset_index(drop=True, inplace=True)
    
    return opt_atm, copt, popt, fut;

def perf_pccrss(dt_strtg_begin_buf, dt_strg_end_buf, dt_react_obs, dt_react_hold, dp_lc, dp_pt, dp_pt_buf, unit, opt_atm):

    dt_strg_end_buf = 10*60 + dt_strg_end_buf    #전략 종료 시간 버퍼

    ent_dp = 0.5         # 진입 가격 변동
    clr_dp = 0.5         # 대응 가격 변동
    
    dp_lc = np.ceil(max(0, dp_lc)/unit) * unit
    dp_pt = np.ceil(max(0, dp_pt)/unit) * unit
    dp_pt_buf = min(dp_pt, (np.ceil(dp_pt_buf)/unit) * unit)

    #atm 자료 시간 오름 차순으로 정렬
    opt_atm = opt_atm.sort_values(by = ['DATE', 'TIME'], ascending=[True, True]);

    #A. 장 시작/종료 시간 추출
    mkt_tm_o = opt_atm.groupby(['DATE'])[['DATE', 'TIME']].head(1);
    mkt_tm_c = opt_atm.groupby(['DATE'])[['DATE', 'TIME']].tail(1);
    mkt_tm = pd.merge(mkt_tm_o, mkt_tm_c, how = 'inner', on = ['DATE'], suffixes=['_O', '_C']);

    strtgy_opt = pd.merge(opt_atm, mkt_tm, how = 'inner', on = ['DATE']);

    #Z. 전략 실행
    # atm_strk_cur
    # Dominant_opt
    #손익
    tot_pl = 0
    fee = 0
    fee_rt = 0.003/100
    exec = pd.DataFrame(columns=['DATE', 'TIME', 'POS_TYPE', 'TR', 'PL', 'FEE'])
    
    #position
    pos = 0
    pos_type = ''
    
    pr_ent = None # 진입가격
    react_obs_tm = datetime.min
    react_hold_tm = datetime.min    
    pr_h = -np.inf
    pr_l = np.inf
    
    for idx, atm_i in strtgy_opt.iterrows():
        tm_i = datetime.combine(atm_i['DATE'], atm_i['TIME'])
        pr_i = atm_i['FUT']
        pr_o_i = atm_i['FUT_O']
        pr_h_i = atm_i['FUT_H']
        pr_l_i = atm_i['FUT_L']
        
        #장 시작 후, 일정 시간은 거래 skip
        mkt_o_tm = datetime.combine(atm_i['DATE'], atm_i['TIME_O']) 
        if tm_i < mkt_o_tm + timedelta(seconds=dt_strtg_begin_buf):
            continue
        
        #장 종료 전, 청산
        mkt_c_tm = datetime.combine(atm_i['DATE'], atm_i['TIME_C']) 
        if pos != 0 and mkt_c_tm - timedelta(seconds=dt_strg_end_buf) <= tm_i:
            
            pl_clr_i = np.sign(pos) * (pr_i - pr_ent)          
            fee_i = pr_i * fee_rt
            tot_pl = tot_pl + pl_clr_i - fee_i    
            
            pos = 0
            exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'CLR', 'PL' : pl_clr_i, 'FEE' : fee_i}])
            if len(exec) == 0:
                exec = exec_i
            else:
                exec = pd.concat([exec, exec_i])
            
            #초기화
            pos = 0              
            pos_type = ''
            
            #장종료 전 청산 시, 대응관찰/유보시간 초기화
            react_obs_tm = datetime.min
            react_hold_tm = datetime.min            
            pr_ent = None # 진입가격
            pr_h = -np.inf
            pr_l = np.inf
            
            continue
        
        #장 종료 전, 일정 시간은 거래 skip 
        if mkt_c_tm - timedelta(seconds=dt_strg_end_buf) <= tm_i:
            continue
                
        pr_h = max(pr_h, pr_h_i)
        pr_l = min(pr_l, pr_l_i)
        
        opt_dmnt_prv_i = atm_i['OPT_DMNT_PRV']
        opt_dmnt_i = atm_i['OPT_DMNT']
        
        #1.1 손절 가격대이면, 손절(대응시간 변경, 가격 초기화, 손익 반영)
        pr_lc_i = 0
        if (pos > 0 and pr_l <= (pr_ent - dp_lc)):
            pr_lc_i = min(pr_ent - dp_lc, pr_o_i)
        elif (pos < 0 and (pr_ent + dp_lc) <= pr_h):
            pr_lc_i = max(pr_ent + dp_lc, pr_o_i)
            
        if pr_lc_i != 0: 
            
            pl_lc_i = np.sign(pos) * (pr_lc_i - pr_ent)          
            fee_i = pr_lc_i * fee_rt
            tot_pl = tot_pl + pl_lc_i - fee_i
            pos = 0              

            exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'LC', 'PL' : pl_lc_i, 'FEE' : fee_i}])
            if len(exec) == 0:
                exec = exec_i
            else:
                exec = pd.concat([exec, exec_i])

            #손절 시, 대응관찰/유보시간 초기화
            react_obs_tm = tm_i + timedelta(seconds = dt_react_obs)
            react_hold_tm = tm_i + timedelta(seconds = dt_react_hold)
            
            pr_ent = pr_lc_i
            pr_h = pr_lc_i
            pr_l = pr_lc_i
           
            #초기화
            pos_type = ''
            
            continue    
        
        #1.2 익절 구간이면
        pr_pt_i = 0
        if (pos > 0 and pr_h >= pr_ent + dp_pt):
            pr_pt_i = max(pr_h, pr_ent + dp_pt) - dp_pt_buf
            
        elif (pos < 0 and pr_l <= pr_ent - dp_pt):
            pr_pt_i = min(pr_h, pr_ent - dp_pt) + dp_pt_buf
        
        #A. 익절 구간이고, 현재 가격이 익절 실행 가격이면
        if pr_pt_i != 0 and ((0 < pos and pr_l_i <= pr_pt_i) or (pos < 0 and pr_pt_i <= pr_h_i )) :
            pl_pt_i = np.sign(pos) * (pr_pt_i - pr_ent)          
            fee_i = pr_pt_i * fee_rt
            tot_pl = tot_pl + pl_pt_i - fee_i
            
            pos = 0              
            exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'PT', 'PL' : pl_pt_i, 'FEE' : fee_i}])
            if len(exec) == 0:
                exec = exec_i
            else:
                exec = pd.concat([exec, exec_i])

            #익절 시, 대응관찰/유보시간 초기화
            react_obs_tm = datetime.min
            react_hold_tm = datetime.min
            
            pr_ent = pr_pt_i
            pr_h = pr_pt_i
            pr_l = pr_pt_i
            
            #초기화
            pos_type = ''
            continue    
          
        #2.1 대응유보 시간 이내이면, 
        if tm_i < react_hold_tm:
            #아무 작업하지 않음    
            continue
        
        #2.2 대응유보시간 종료했으면 대응유보시간 초기화
        react_hold_tm = datetime.min  
        
        #3.1 대응관찰시간 이내이면 이후
        if tm_i < react_obs_tm:
            #아무 작업하지 않음    
            continue
        
        #3.2 대응관찰 시간 이후, PUT/CALL Cross가 발생했다면, 대응관찰 시작
        react_obs_tm = datetime.min

        if (opt_dmnt_prv_i != opt_dmnt_i) \
            or (pos != 0 and ((pos_type != 'S' and opt_dmnt_i == 'P') or (pos_type != 'L' and opt_dmnt_i == 'C'))) :
                
            if opt_dmnt_i == 'P':
                pos_type = 'S'            
            elif opt_dmnt_i == 'C':
                pos_type = 'L'            
            
            #대응관찰 종료 시간 설정 후, 관찰 시작
            react_obs_tm = tm_i + timedelta(seconds = dt_react_obs)

        
        #3.3 대응관찰시간 종료됐으면, 대응관찰시간 초과 후 옵션크로스 신호의 진위여부에 따라서 대응
                
        #대응관찰시간 초기화
        react_obs_tm = datetime.min
                    
        pl_i = 0   
        
        # 대응관찰 전/후 PUT 우세가 유지되고 있다면
        if pos_type == 'S' and opt_dmnt_i == 'P':
            
            #현재 SHORT 포지션이면, 
            if pos < 0:
                #아무 작업하지 않음
                continue
            
            #현재 LONG 포지션이면, 
            if pos > 0:
                #매도를 통한 손익 실현
                pos = 0
                pos_type = ''
                
                pl_i = (pr_i - pr_ent)
                fee_i = pr_i * fee_rt
                tot_pl = tot_pl + pl_i - fee_i

                exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'CLR', 'PL' : pl_i, 'FEE' : fee_i}])
                if len(exec) == 0:
                    exec = exec_i
                else:
                    exec = pd.concat([exec, exec_i])
                
            #SHORT 포지션 진입
            pos = -1
            pos_type = 'S'
            
            fee_i = pr_i * fee_rt
            tot_pl = tot_pl - fee_i
            exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'ES', 'PL' : 0, 'FEE' : fee_i}])            
            if len(exec) == 0:
                exec = exec_i
            else:
                exec = pd.concat([exec, exec_i])
            
            react_hold_tm = tm_i + timedelta(seconds = dt_react_hold)
            pr_ent = pr_i
            pr_h = pr_i
            pr_l = pr_i                     
                    
            continue
        
        # 대응관찰 전/후 CALL 우세가 유지되고 있다면
        if pos_type == 'L' and opt_dmnt_i == 'C':
        
            #현재 LONG 포지션이면, 
            if pos > 0:
                #아무 작업하지 않음
                continue
            
            #현재 SHORT 포지션이면, 
            if pos < 0:
                #매수를 통한 손익 실현
                pos = 0
                pos_type = ''
                
                pl_i = (pr_ent - pr_i)                
                fee_i = pr_i * fee_rt
                tot_pl = tot_pl + pl_i - fee_i
                
                exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'CLR', 'PL' : pl_i, 'FEE' : fee_i}])
                if len(exec) == 0:
                    exec = exec_i
                else:
                    exec = pd.concat([exec, exec_i])

            #LONG 포지션 진입
            pos = 1
            pos_type = 'L'
            
            fee_i = pr_i * fee_rt
            tot_pl = tot_pl - fee_i
            exec_i = pd.DataFrame([{'DATE' : tm_i.date(), 'TIME' : tm_i.time(), 'POS_TYPE' : pos_type, 'POS' : pos, 'TR' : 'EL', 'PL' : 0, 'FEE' : fee_i}])         

            if len(exec) == 0:
                exec = exec_i
            else:
                exec = pd.concat([exec, exec_i])
                
            react_hold_tm = tm_i + timedelta(seconds = dt_react_hold)
            pr_ent = pr_i
            pr_h = pr_i
            pr_l = pr_i 
                     
            continue       
    return [tot_pl, exec]

def _perf_pccrss(x, unit, def_param, opt_atm):
    
    param = []
    j = 0
    for i in range(def_param) :
        
        param_i = def_param[i]
        
        if param_i is None:
            param_i = x[j]
            j = j + 1
                
        param.append(param_i)    
         
    [pl, exec] = perf_pccrss(param[0], param[1], param[2], param[3], param[4], param[5], param[6], opt_atm, unit)
    
    return -1 * pl

def print_fun(x, unit, def_param, opt_atm, convergence):
    
    param = []
    j = 0
    for i in range(def_param) :
        
        param_i = def_param[i]
        
        if param_i is None:
            param_i = x[j]
            j = j + 1
                
        param.append(param_i)    
    
    param = np.round(param, 2)
    
    print("PL = %+.4f (dt_strtg_begin_buf = %+.2f, dt_strg_end_buf = %+.2f, dt_react_obs =  = %+.2f, react_hold_dt = %+.2f" \
        ", dp_lc = %+.2f, dp_pt = %+.2f, dp_pt_buf = %+.2f)" \
            % (-_perf_pccrss(x, unit, def_param, opt_atm)
                            , param[0], param[1], param[2], param[3], param[4], param[5], param[6]))

def est_pccrss(unit, def_param, opt_atm):

    bnds = ((0, 60*60), (0, 60*60), (0, 60*60), (0, 10), (0, 10), (0, 10))
    
    x0 = [3*60, 3*60, 1*60, 0.5, 1.5, 0.5]
    strategy = ['best1bin', 'best1exp', 'rand1exp', 'randtobest1exp', 'currenttobest1exp', 'best2exp', 'rand2exp'
                , 'randtobest1bin', 'currenttobest1bin', 'best2bin', 'rand2bin', 'rand1bin']
               
    x_init = x0
    
    opt_best = np.inf
    custom_args = [est_opt_atm, unit, def_param]
    i = 0
    strategy_i = strategy[i]
    print("------------------- strategy : %s -------------------" % (strategy_i))
    opt = spo.differential_evolution(func = _perf_pccrss, args = custom_args, bounds = bnds, x0 = x_init, constraints=(), strategy = strategy_i
                                 , seed = i, disp = True, callback = lambda xk, convergence: print_fun(xk, est_opt_atm, unit, def_param, convergence)
                                 , polish = False, updating = 'deferred', workers = -1, maxiter = 10000)

    # while True:
        
    #     for i in range(len(strategy)):
    #         strategy_i = strategy[i]
    #         print("------------------- strategy : %s -------------------" % (strategy_i))
    #         opt = spo.differential_evolution(func = _dp_pt_bufcrss, args = custom_args, bounds = bnds, x0 = x_init, constraints=(), strategy = strategy_i
    #                                      , seed = i, disp = True, callback = lambda xk, convergence: print_fun(xk, est_opt_atm, convergence), polish = False, updating = 'deferred', workers = -1, maxiter = 3)
        
    #         x_init = opt.x
    #     if opt.fun >= opt_best:
    #         break
    #     opt_best = opt.fun

    return opt.x


def bktest_pccrss(est_opt_atm, perf_opt_atm, unit = 0.05, def_param = [None, None, None, None, None, None, None]):
    x = est_pccrss(est_opt_atm)
    
    param = []
    j = 0
    for i in range(def_param) :
        
        param_i = def_param[i]
        
        if param_i is None:
            param_i = x[j]
            j = j + 1
                
        param.append(param_i)    
    
    param = np.round(param, 2)
    
    [pl, exec] = perf_pccrss(param[0], param[1], param[2], param[3], param[4], param[5], param[6], unit, est_opt_atm)
    
    param = {'dt_strtg_begin_buf' : param[0], 'dt_strg_end_buf' : param[1], 
             'react_wait_dt' : param[2], 
             'react_hold_dt' : param[3], 
             'dp_lc' : param[4], 
             'dp_pt' : param[5], 'dp_pt_buf' : param[6]
            }
    return {'PL' : pl, 'EXEC' : exec, 'PARAM' : param}


