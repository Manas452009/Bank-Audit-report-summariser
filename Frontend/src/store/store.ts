import { configureStore } from "@reduxjs/toolkit";
import authReducer from "./authSlice";

export type RootState = {
  auth: ReturnType<typeof authReducer>;
};

export type AppDispatch = typeof store.dispatch;

const loadState = (): RootState | undefined => {
  try {
    const serializedState = localStorage.getItem('authState');
    if (serializedState === null) {
      return undefined;
    }
    return { auth: JSON.parse(serializedState) };
  } catch (err) {
    console.warn('Failed to load state from localStorage:', err);
    return undefined;
  }
};

const saveState = (state: RootState) => {
  try {
    localStorage.setItem('authState', JSON.stringify(state.auth));
  } catch (err) {
    console.warn('Failed to save state to localStorage:', err);
  }
};

export const store = configureStore({
  reducer: {
    auth: authReducer,
  },
  preloadedState: loadState(),
});

store.subscribe(() => {
  saveState(store.getState() as RootState);
});
