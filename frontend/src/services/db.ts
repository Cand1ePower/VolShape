export interface LocalWorkout {
  id: string;
  title: string;
  exercises: string;
  targetDate: string;
  synced: number;
}

const _mem: Record<string, string> = {};

function _isWeb(): boolean {
  return typeof window !== 'undefined' && !!window.localStorage;
}

function _webGet(k: string): string | null { return localStorage.getItem(k); }
function _webSet(k: string, v: string): void { localStorage.setItem(k, v); }

async function saveWorkoutOffline(id: string, title: string, exercises: any[], targetDate: string): Promise<boolean> {
  try {
    const data = JSON.stringify({ title, exercises, targetDate });
    if (_isWeb()) { _webSet(id, data); } else { _mem[id] = data; }
    return true;
  } catch { return false; }
}

async function getUnsyncedWorkouts(): Promise<LocalWorkout[]> { return []; }
async function markAsSynced(id: string): Promise<boolean> { return true; }

export const localDB = { init: () => Promise.resolve(), saveWorkoutOffline, getUnsyncedWorkouts, markAsSynced };
