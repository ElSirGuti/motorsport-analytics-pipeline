import { setCursorDistance } from '../api/cursorStore';

export function useCursorWriter() {
  return {
    onMouseMove: (state) => { if (state?.activeLabel != null) setCursorDistance(state.activeLabel); },
    onMouseLeave: () => setCursorDistance(null),
  };
}
