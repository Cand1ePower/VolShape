import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { localDB } from '@/services/db';

export interface PlanExercise {
  name: string;
  sets: number;
  reps: string;
  weight?: string;
  notes?: string;
}

export interface ActivePlan {
  title: string;
  exercises: PlanExercise[];
  disclaimer?: string;
  createdAt: Date;
}

export interface CompletedPlan extends ActivePlan {
  completedAt: Date;
  completedSets: number;
  totalSets: number;
}

interface PlanContextType {
  activePlan: ActivePlan | null;
  setActivePlan: (plan: ActivePlan | null) => void;
  completedExercises: Set<string>;
  toggleComplete: (exerciseIndex: number, setIndex: number) => void;
  completePlan: () => void;
  resetPlan: () => void;
  trainingHistory: CompletedPlan[];
}

const PlanContext = createContext<PlanContextType>({
  activePlan: null,
  setActivePlan: () => {},
  completedExercises: new Set(),
  toggleComplete: () => {},
  completePlan: () => {},
  resetPlan: () => {},
  trainingHistory: [],
});

export function usePlan() {
  return useContext(PlanContext);
}

export function PlanProvider({ children }: { children: React.ReactNode }) {
  const [activePlan, setActivePlanState] = useState<ActivePlan | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [trainingHistory, setTrainingHistory] = useState<CompletedPlan[]>([]);
  const dbReady = useRef(false);

  useEffect(() => {
    localDB.init().then(() => { dbReady.current = true; });
  }, []);

  const setActivePlan = useCallback((plan: ActivePlan | null) => {
    setActivePlanState(plan);
    setCompleted(new Set());
  }, []);

  const toggleComplete = useCallback((exIdx: number, setIdx: number) => {
    const key = `${exIdx}-${setIdx}`;
    setCompleted(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const completePlan = useCallback(() => {
    if (!activePlan) return;
    const totalSets = activePlan.exercises.reduce((s, e) => s + e.sets, 0);
    const completedPlan: CompletedPlan = {
      ...activePlan,
      completedAt: new Date(),
      completedSets: completed.size,
      totalSets,
    };
    setTrainingHistory(prev => [completedPlan, ...prev]);
    // Persist to local DB
    if (dbReady.current) {
      localDB.saveWorkoutOffline(
        `${Date.now()}`,
        activePlan.title,
        activePlan.exercises,
        new Date().toISOString().split('T')[0],
      ).catch(() => {});
    }
    setActivePlanState(null);
    setCompleted(new Set());
  }, [activePlan, completed]);

  const resetPlan = useCallback(() => {
    setActivePlanState(null);
    setCompleted(new Set());
  }, []);

  return (
    <PlanContext.Provider value={{ activePlan, setActivePlan, completedExercises: completed, toggleComplete, completePlan, resetPlan, trainingHistory }}>
      {children}
    </PlanContext.Provider>
  );
}
