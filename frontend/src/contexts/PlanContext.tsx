import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { Platform } from 'react-native';
import { localDB } from '@/services/db';
import { useAuth } from './AuthContext';

export interface PlanExercise {
  name: string;
  sets: number;
  reps: string;
  weight?: string;
  notes?: string;
}

export interface ActivePlan {
  planId?: string; // 后端数据库中物理唯一的计划 ID
  title: string;
  exercises: PlanExercise[];
  disclaimer?: string;
  createdAt: Date;
}

export interface CompletedPlan extends ActivePlan {
  completedAt: Date;
  completedSets: number;
  totalSets: number;
  completedKeys?: string[];
}

interface PlanContextType {
  activePlan: ActivePlan | null;
  setActivePlan: (plan: ActivePlan | null) => void;
  completedExercises: Set<string>;
  toggleComplete: (exerciseIndex: number, setIndex: number) => void;
  completePlan: () => void;
  resetPlan: () => void;
  trainingHistory: CompletedPlan[];
  planStatusMap: Record<string, 'active' | 'training' | 'completed'>; // 全局卡片状态映射
  syncWorkoutOnLogin: () => Promise<void>;
  applyWorkoutOnBackend: (planId: string, plan: ActivePlan) => Promise<void>;
}

const PlanContext = createContext<PlanContextType>({
  activePlan: null,
  setActivePlan: () => {},
  completedExercises: new Set(),
  toggleComplete: () => {},
  completePlan: () => {},
  resetPlan: () => {},
  trainingHistory: [],
  planStatusMap: {},
  syncWorkoutOnLogin: async () => {},
  applyWorkoutOnBackend: async () => {},
});

export function usePlan() {
  return useContext(PlanContext);
}

export function PlanProvider({ children }: { children: React.ReactNode }) {
  const { token, isLoggedIn } = useAuth();
  const [activePlan, setActivePlanState] = useState<ActivePlan | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [trainingHistory, setTrainingHistory] = useState<CompletedPlan[]>([]);
  const [planStatusMap, setPlanStatusMap] = useState<Record<string, 'active' | 'training' | 'completed'>>({});
  
  const dbReady = useRef(false);

  // 获取后台 API URL 辅助器
  const getWorkoutUrl = (path: string) => {
    const baseUrl = Platform.OS === 'android' ? 'http://192.168.10.7:8000' : 'http://localhost:8000';
    return `${baseUrl}${path}`;
  };

  useEffect(() => {
    localDB.init().then(() => { dbReady.current = true; });
  }, []);

  // 🌟 手动同步与现场还原接口
  const syncWorkoutOnLogin = useCallback(async () => {
    if (!isLoggedIn || !token) {
      setActivePlanState(null);
      setCompleted(new Set());
      setTrainingHistory([]);
      setPlanStatusMap({});
      return;
    }

    try {
      // 1. 获取用户所有卡片的状态映射
      const statusResp = await fetch(getWorkoutUrl('/api/workout/all_status'), {
        headers: { Authorization: `Bearer ${token}`, Connection: 'close' }
      });
      if (statusResp.ok) {
        const data = await statusResp.json(); // 🌟 修复之前的 await 布尔值错误语法，保障安全解析
        if (data.status_map) {
          setPlanStatusMap(data.status_map);
        }
      }

      // 2. 获取用户的训练历史
      const historyResp = await fetch(getWorkoutUrl('/api/workout/history'), {
        headers: { Authorization: `Bearer ${token}`, Connection: 'close' }
      });
      if (historyResp.ok) {
        const data = await historyResp.json();
        if (data.history) {
          const historyList: CompletedPlan[] = data.history.map((p: any) => ({
            planId: p.id,
            title: p.plan_json.title || '今日训练计划',
            exercises: p.plan_json.exercises || [],
            disclaimer: p.plan_json.disclaimer,
            createdAt: new Date(p.target_date),
            completedAt: new Date(p.target_date), // 简化处理，使用目标日期作为完成时间
            completedSets: p.completion_data?.completed_sets || 0,
            totalSets: p.completion_data?.total_sets || 0,
            completedKeys: p.completion_data?.completed_keys || [],
          }));
          setTrainingHistory(historyList);
        }
      }

      // 3. 还原当前正在进行的训练（还原现场防强刷）
      const activeResp = await fetch(getWorkoutUrl('/api/workout/active'), {
        headers: { Authorization: `Bearer ${token}`, Connection: 'close' }
      });
      if (activeResp.ok) {
        const data = await activeResp.json();
        if (data.plan) {
          const p = data.plan;
          setActivePlanState({
            planId: p.id,
            title: p.plan_json.title || '今日训练计划',
            exercises: p.plan_json.exercises || [],
            disclaimer: p.plan_json.disclaimer,
            createdAt: new Date(p.target_date),
          });

          // 从 completion_data 里还原已完成组打卡进度
          if (p.completion_data && p.completion_data.completed_keys) {
            setCompleted(new Set(p.completion_data.completed_keys));
          } else {
            setCompleted(new Set());
          }
        } else {
          setActivePlanState(null);
          setCompleted(new Set());
        }
      }
    } catch (e) {
      console.error('[Workout Sync Error] Failed to sync training state on login/refresh:', e);
    }
  }, [isLoggedIn, token]);

  // 🌟 当登录/登出状态改变时，自动发起多页面物理同步或极致状态重置
  useEffect(() => {
    if (!isLoggedIn) {
      setActivePlanState(null);
      setCompleted(new Set());
      setTrainingHistory([]);
      setPlanStatusMap({});
    } else {
      syncWorkoutOnLogin();
    }
  }, [isLoggedIn, syncWorkoutOnLogin]);

  const setActivePlan = useCallback((plan: ActivePlan | null) => {
    setActivePlanState(plan);
    setCompleted(new Set());
  }, []);

  // 🌟 点击“应用计划并开始训练”时的物理绑定
  const applyWorkoutOnBackend = useCallback(async (planId: string, plan: ActivePlan) => {
    if (!isLoggedIn || !token) return;
    try {
      const planJson = {
        title: plan.title,
        exercises: plan.exercises,
        disclaimer: plan.disclaimer,
        plan_id: planId
      };
      
      const resp = await fetch(getWorkoutUrl('/api/workout/apply'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Connection: 'close'
        },
        body: JSON.stringify({ plan_id: planId, plan_json: planJson }), // 🌟 包含 plan_json 以同步延迟落库
      });
      if (resp.ok) {
        // 设置前端活跃计划并清空进度
        setActivePlanState({ ...plan, planId });
        setCompleted(new Set());
        // 实时更新全局状态机映射
        setPlanStatusMap(prev => ({
          ...prev,
          [planId]: 'training',
        }));
      } else {
        console.error('[Apply Workout Failed] Server returned non-200');
      }
    } catch (e) {
      console.error('[Apply Workout Error] Connection failure:', e);
    }
  }, [isLoggedIn, token]);

  const toggleComplete = useCallback((exIdx: number, setIdx: number) => {
    const key = `${exIdx}-${setIdx}`;
    setCompleted(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);

      // 🌟 进度实时同步暂存 (防闪退机制) —— 改为调用全新的 /api/workout/save_progress 进度落库接口！
      // 这能保证既同步了打卡明细进度，又【强制维持 status = 'training' 不变】，彻底解决了强刷凭空消失的重大 Bug！
      if (activePlan?.planId && token) {
        const completedKeys = Array.from(next);
        const totalSets = activePlan.exercises.reduce((s, e) => s + e.sets, 0);
        fetch(getWorkoutUrl('/api/workout/save_progress'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Connection: 'close'
          },
          body: JSON.stringify({
            plan_id: activePlan.planId,
            completion_data: {
              exercises: activePlan.exercises,
              completed_sets: completedKeys.length,
              completed_keys: completedKeys,
              total_sets: totalSets,
            },
          }),
        }).catch(() => {});
      }

      return next;
    });
  }, [activePlan, token]);

  // 🌟 完成训练：同步至后端数据库并记录历史 (封档归仓)
  const completePlan = useCallback(async () => {
    if (!activePlan || !activePlan.planId || !token) return;
    
    const planId = activePlan.planId;
    const totalSets = activePlan.exercises.reduce((s, e) => s + e.sets, 0);
    const completedKeys = Array.from(completed);
    
    const completedPlan: CompletedPlan = {
      ...activePlan,
      completedAt: new Date(),
      completedSets: completedKeys.length,
      totalSets,
      completedKeys,
    };

    try {
      // 1. 同步物理数据库修改状态为 completed (物理归档)
      const resp = await fetch(getWorkoutUrl('/api/workout/complete'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Connection: 'close'
        },
        body: JSON.stringify({
          plan_id: planId,
          completion_data: {
            exercises: activePlan.exercises,
            completed_sets: completedKeys.length,
            completed_keys: completedKeys,
            total_sets: totalSets,
          },
        }),
      });

      if (resp.ok) {
        // 更新历史记录与计划映射状态
        setTrainingHistory(prev => [completedPlan, ...prev]);
        setPlanStatusMap(prev => ({
          ...prev,
          [planId]: 'completed',
        }));

        // 2. 本地离线持久化备份
        if (dbReady.current) {
          localDB.saveWorkoutOffline(
            `${Date.now()}`,
            activePlan.title,
            activePlan.exercises,
            new Date().toISOString().split('T')[0],
          ).catch(() => {});
        }

        // 3. 复位前端状态
        setActivePlanState(null);
        setCompleted(new Set());
      } else {
        console.error('[Complete Workout Failed] Server returned non-200');
      }
    } catch (e) {
      console.error('[Complete Workout Error] Connection failure:', e);
    }
  }, [activePlan, completed, token]);

  const resetPlan = useCallback(async () => {
    if (activePlan?.planId && token) {
      const planId = activePlan.planId;
      setPlanStatusMap(prev => ({
        ...prev,
        [planId]: 'active', // 🌟 重置为可应用状态，聊天框同步更新！
      }));

      try {
        await fetch(getWorkoutUrl('/api/workout/abandon'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            Connection: 'close'
          },
          body: JSON.stringify({ plan_id: planId, completion_data: {} }),
        });
      } catch (e) {
        console.error('[Abandon Workout Failed]', e);
      }
    }
    setActivePlanState(null);
    setCompleted(new Set());
  }, [activePlan, token]);

  return (
    <PlanContext.Provider value={{
      activePlan,
      setActivePlan,
      completedExercises: completed,
      toggleComplete,
      completePlan,
      resetPlan,
      trainingHistory,
      planStatusMap,
      syncWorkoutOnLogin,
      applyWorkoutOnBackend
    }}>
      {children}
    </PlanContext.Provider>
  );
}
