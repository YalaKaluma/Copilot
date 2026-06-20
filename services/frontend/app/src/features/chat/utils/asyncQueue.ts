export interface AsyncSerialTaskQueue {
  enqueue<T>(task: () => Promise<T>): Promise<T>;
  /**
   * Enqueue a task to run before any already-queued normal tasks (after current task).
   * Clears the normal queue so no older task runs after this one (e.g. avoid overwriting 'done' with an older stage).
   */
  enqueuePriority<T>(task: () => Promise<T>): Promise<T>;
}

/**
 * Runs async tasks one-at-a-time, preserving enqueue order.
 * Priority tasks run before normal tasks that were enqueued earlier.
 * Each task starts after the previous one settles (success or error).
 */
export function createAsyncSerialTaskQueue(): AsyncSerialTaskQueue {
  let tail: Promise<void> = Promise.resolve();
  let isScheduled = false;
  const normalQueue: Array<QueueEntry> = [];
  const priorityQueue: Array<QueueEntry> = [];

  type QueueEntry = {
    run: () => Promise<void>;
    cancel: () => void;
  };

  const createPurgedTaskError = (): Error => {
    const err = new Error('Task canceled because priority work was enqueued');
    err.name = 'AsyncQueueTaskCanceledError';
    return err;
  };

  function processNext(): void {
    const entry = priorityQueue.shift() ?? normalQueue.shift();
    if (!entry) {
      isScheduled = false;
      return;
    }
    tail = tail
      .then(() => entry.run())
      .then(
        () => {
          isScheduled = false;
          processNext();
        },
        () => {
          isScheduled = false;
          processNext();
        }
      );
    isScheduled = true;
  }

  function maybeSchedule(): void {
    if (!isScheduled && (priorityQueue.length > 0 || normalQueue.length > 0)) {
      processNext();
    }
  }

  function enqueue<T>(task: () => Promise<T>, priority: boolean): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      let settled = false;
      const entry: QueueEntry = {
        run: async (): Promise<void> => {
          try {
            const result = await task();
            settled = true;
            resolve(result);
          } catch (err) {
            settled = true;
            reject(err);
            throw err;
          }
        },
        cancel: (): void => {
          if (settled) {
            return;
          }
          settled = true;
          reject(createPurgedTaskError());
        },
      };
      if (priority) {
        while (normalQueue.length > 0) {
          normalQueue.shift()?.cancel();
        }
        priorityQueue.push(entry);
      } else {
        normalQueue.push(entry);
      }
      maybeSchedule();
    });
  }

  return {
    enqueue<T>(task: () => Promise<T>): Promise<T> {
      return enqueue(task, false);
    },
    enqueuePriority<T>(task: () => Promise<T>): Promise<T> {
      return enqueue(task, true);
    },
  };
}
