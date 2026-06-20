import { describe, expect, it } from 'vitest';
import { createAsyncSerialTaskQueue } from './asyncQueue';

describe('createAsyncSerialTaskQueue', () => {
  it('runs tasks sequentially in enqueue order', async () => {
    const queue = createAsyncSerialTaskQueue();
    const events: string[] = [];

    let releaseFirst: (() => void) | null = null;
    const firstGate = new Promise<void>((resolve) => {
      releaseFirst = resolve;
    });

    const first = queue.enqueue(async () => {
      events.push('first:start');
      await firstGate;
      events.push('first:end');
      return 1;
    });

    const second = queue.enqueue(async () => {
      events.push('second');
      return 2;
    });

    releaseFirst?.();

    await expect(first).resolves.toBe(1);
    await expect(second).resolves.toBe(2);
    expect(events).toEqual(['first:start', 'first:end', 'second']);
  });

  it('continues processing after a task fails', async () => {
    const queue = createAsyncSerialTaskQueue();

    await expect(
      queue.enqueue(async () => {
        throw new Error('boom');
      })
    ).rejects.toThrow('boom');

    await expect(
      queue.enqueue(async () => 42)
    ).resolves.toBe(42);
  });

  it('runs priority before remaining normal tasks and clears normal queue so only priority runs after current', async () => {
    const queue = createAsyncSerialTaskQueue();
    const events: string[] = [];

    let releaseFirst: (() => void) | null = null;
    const firstGate = new Promise<void>((resolve) => {
      releaseFirst = resolve;
    });

    const normal1 = queue.enqueue(async () => {
      events.push('normal1:start');
      await firstGate;
      events.push('normal1:end');
      return 1;
    });

    const normal2 = queue.enqueue(async () => {
      events.push('normal2');
      return 2;
    });

    const priority = queue.enqueuePriority(async () => {
      events.push('priority');
      return 3;
    });

    releaseFirst?.();

    await expect(normal1).resolves.toBe(1);
    await expect(normal2).rejects.toThrow('Task canceled because priority work was enqueued');
    await expect(priority).resolves.toBe(3);
    expect(events).toEqual(['normal1:start', 'normal1:end', 'priority']);
  });

  it('clears normal queue when priority is enqueued so skipped tasks never run', async () => {
    const queue = createAsyncSerialTaskQueue();
    const events: string[] = [];

    let releaseFirst: (() => void) | null = null;
    const firstGate = new Promise<void>((resolve) => {
      releaseFirst = resolve;
    });

    queue.enqueue(async () => {
      events.push('normal1:start');
      await firstGate;
      events.push('normal1:end');
      return 1;
    });

    const normal2 = queue.enqueue(async () => {
      events.push('normal2');
      return 2;
    });

    const priority = queue.enqueuePriority(async () => {
      events.push('priority');
      return 3;
    });

    releaseFirst?.();

    await expect(normal2).rejects.toThrow('Task canceled because priority work was enqueued');
    await expect(priority).resolves.toBe(3);
    expect(events).toEqual(['normal1:start', 'normal1:end', 'priority']);
  });
});
