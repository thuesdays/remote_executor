# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import sys
import types
import time
import multiprocessing
from functools import wraps
from concurrent import futures

GTask = MultiGTask = None
POOL_TIMEOUT = 0.02


class ReturnResult(Exception):
    def __init__(self, result):
        super(ReturnResult, self).__init__()
        self.result = result


class Engine(object):
    def __init__(self, pool_timeout=POOL_TIMEOUT):
        self.pool_timeout = pool_timeout
        self.main_app = None

    def async(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            gen = func(*args, **kwargs)
            if isinstance(gen, types.GeneratorType):
                return self.create_runner(gen).run()
        return wrapper

    def create_runner(self, gen):
        return Runner(self, gen)

    def update_gui(self):
        time.sleep(self.pool_timeout)


class Runner(object):
    def __init__(self, engine, gen):
        self.engine = engine
        self.gen = gen

    def run(self):
        gen = self.gen
        try:
            task = next(gen)  # start generator and receive first task
        except StopIteration:
            return
        while True:
            try:
                if isinstance(task, (list, tuple)):
                    assert len(task), "Empty tasks sequence"
                    first_task = task[0]
                    if isinstance(first_task, ProcessTask):
                        task = MultiProcessTask(task)
                    elif GTask and isinstance(first_task, GTask):
                        task = MultiGTask(task)
                    else:
                        task = MultiTask(task)

                with task.executor_class(task.max_workers) as executor:
                    if isinstance(task, MultiTask):
                        task = self._execute_multi_task(gen, executor, task)
                    else:
                        task = self._execute_single_task(gen, executor, task)
            except StopIteration:
                break
            except ReturnResult as e:
                gen.close()
                return e.result

    def _execute_single_task(self, gen, executor, task):
        future = executor.submit(task)
        while True:
            try:
                result = future.result(self.engine.pool_timeout)
            except futures.TimeoutError:
                self.engine.update_gui()
            # TODO canceled error
            except Exception:
                return gen.throw(*sys.exc_info())
            else:
                return gen.send(result)

    def _execute_multi_task(self, gen, executor, task):
        if task.unordered:
            results_gen = self._execute_multi_gen_task(gen, executor, task)
            return gen.send(results_gen)

        future_tasks = [executor.submit(t) for t in task.tasks]
        while True:
            if not task.wait(executor, future_tasks, self.engine.pool_timeout):
                self.engine.update_gui()
            else:
                break
        if task.skip_errors:
            results = []
            for f in future_tasks:
                try:
                    results.append(f.result())
                except Exception:
                    pass
        else:
            try:
                results = [f.result() for f in future_tasks]
            except Exception:
                return gen.throw(*sys.exc_info())
        return gen.send(results)

    def _execute_multi_gen_task(self, gen, executor, task):
        unfinished = set(executor.submit(t) for t in task.tasks)
        while unfinished:
            if not task.wait(executor, unfinished, self.engine.pool_timeout):
                self.engine.update_gui()
            done = set(f for f in unfinished if f.done())
            for f in done:
                try:
                    result = f.result()
                except Exception:
                    if not task.skip_errors:
                        raise
                else:
                    yield result
            unfinished.difference_update(done)


def return_result(result):
    raise ReturnResult(result)


class QtEngine(Engine):
    QtCore = None

    def update_gui(self):
        if self.main_app is None:
            self.main_app = self.QtCore.QCoreApplication.instance()
        self.main_app.processEvents(
            self.QtCore.QEventLoop.AllEvents,
            int(self.pool_timeout * 1000)
        )


class PyQtEngine(QtEngine):
    """ PyQt5 support
    """
    QtCore = QtCore


class Task(object):
    executor_class = futures.ThreadPoolExecutor
    max_workers = 1

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def start(self):
        return self.func(*self.args, **self.kwargs)

    __call__ = start

    def __repr__(self):
        return ('<%s(%s, %r, %r)>' %
                (self.__class__.__name__, self.func.__name__,
                 self.args, self.kwargs))


class ProcessTask(Task):
    executor_class = futures.ProcessPoolExecutor


class MultiTask(Task):
    def __init__(self, tasks, max_workers=None, skip_errors=False,
                 unordered=False):
        self.tasks = list(tasks)
        self.max_workers = max_workers if max_workers else len(self.tasks)
        self.skip_errors = skip_errors
        self.unordered = unordered

    def __repr__(self):
        return '<%s(%s)>' % (self.__class__.__name__, self.tasks)

    def wait(self, executor, spawned_futures, timeout=None):
        return not futures.wait(spawned_futures, timeout).not_done


class MultiProcessTask(MultiTask):
    executor_class = futures.ProcessPoolExecutor

    def __init__(self, tasks, max_workers=None, skip_errors=False, **kwargs):
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
        super(MultiProcessTask, self).__init__(
            tasks, max_workers, skip_errors, **kwargs
        )

