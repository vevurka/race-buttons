#!/usr/local/bin/python3.7
import asyncio
import requests
import time
from typing import Callable
from functools import partial
from dataclasses import dataclass

import RPi.GPIO as GPIO

BOUNCETIME = 200

START_BUTTON = 23
LOCK_SWITCH = 24
ACC1_SWITCH = 5
ACC2_SWITCH = 16
ACC3_SWITCH = 17


class MultiLock:
    lock_switch = asyncio.Lock()
    acc1_switch = asyncio.Lock()
    acc2_switch = asyncio.Lock()
    acc3_switch = asyncio.Lock()

    @property
    def locks(self) -> dict:
        return {
            LOCK_SWITCH: self.lock_switch,
            ACC1_SWITCH: self.acc1_switch,
            ACC2_SWITCH: self.acc2_switch,
            ACC3_SWITCH: self.acc3_switch,
        }

    def get_lock(self, channel: int) -> asyncio.Lock:
        return self.locks.get(channel)

    def get_state(self, channel: int) -> str:
        lock = self.locks.get(channel)
        return 'on' if lock.locked() else 'off'

    @classmethod
    def flip_lock(cls, func) -> Callable:
        """
        A decorator that changes the state of the given lock.
        The switch can be in "on" or "off" position and the lock should
        track this state.
        """
        async def wrapper(channel: int, lock: MultiLock, state: str, *args, **kwargs):
            if state == 'on':
                await lock.get_lock(channel).acquire()
            elif state == 'off':
                lock.get_lock(channel).release()
            return asyncio.ensure_future(func(channel, lock, state, *args, **kwargs))
        return wrapper
 

def on_event(channel: int, lock: MultiLock, callback: Callable) -> None:
    if channel in (LOCK_SWITCH, ACC1_SWITCH, ACC2_SWITCH, ACC3_SWITCH):
        state = 'off'
        time.sleep(0.1)
        if GPIO.input(channel) == GPIO.LOW:
            state = 'on'
        elif GPIO.input(channel) == GPIO.HIGH:
            state = 'off'
        asyncio.ensure_future(callback(channel, lock, state=state))
    else:
        asyncio.ensure_future(callback(channel, lock))


def set_initial_lock_states(lock):
   """
   Check what is the state of switches when the script starts.
   """
   for channel, switch_lock in lock.locks.items():
       if GPIO.input(channel) == GPIO.LOW:
           asyncio.ensure_future(switch_lock.acquire())


def listener(
        callback_start_button=None,
        callback_lock_switch=None,
        callback_acc1_switch=None,
        callback_acc2_switch=None,
        callback_acc3_switch=None,
    ) -> None:
    lock = MultiLock()
    try:
        loop = asyncio.get_event_loop()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(START_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(LOCK_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ACC1_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ACC2_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ACC3_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        set_initial_lock_states(lock)

        def on_gpio_event(callback, channel):
            loop.call_soon_threadsafe(partial(on_event, channel, lock, callback))

        GPIO.add_event_detect(
            START_BUTTON, GPIO.FALLING,
            callback=partial(on_gpio_event, callback_start_button),
            bouncetime=BOUNCETIME
        )
        GPIO.add_event_detect(
            LOCK_SWITCH, GPIO.RISING,
            callback=partial(on_gpio_event, callback_lock_switch),
            bouncetime=BOUNCETIME
        )
        GPIO.add_event_detect(
            ACC1_SWITCH, GPIO.RISING,
            callback=partial(on_gpio_event, callback_acc1_switch),
            bouncetime=BOUNCETIME
        )
        GPIO.add_event_detect(
            ACC2_SWITCH, GPIO.RISING,
            callback=partial(on_gpio_event, callback_acc2_switch),
            bouncetime=BOUNCETIME
        )
        GPIO.add_event_detect(
            ACC3_SWITCH, GPIO.RISING,
            callback=partial(on_gpio_event, callback_acc3_switch),
            bouncetime=BOUNCETIME
        )

        loop.run_forever()
    finally:
        loop.close()
        GPIO.cleanup()


async def my_callback_button(channel: int, lock: MultiLock, *args, **kwargs) -> None:
    switch_st = lock.get_state(LOCK_SWITCH)
    acc1_st = lock.get_state(ACC1_SWITCH)
    acc2_st = lock.get_state(ACC2_SWITCH)
    acc3_st = lock.get_state(ACC3_SWITCH)
    print(f"Button pressed! LOCK_SWITCH: {switch_st}, ACC1: {acc1_st}, ACC2: {acc2_st}, ACC3: {acc3_st}")
    res = requests.get('http://sireliah.com')
    res.raise_for_status()
    print(res)


@MultiLock.flip_lock
async def my_callback_switch(channel: int, lock: MultiLock, state: str, *args, **kwargs) -> None:
    print("LOCK SWITCH triggered, state: ", lock.get_state(channel))


@MultiLock.flip_lock
async def my_callback_acc1(channel, lock, state, *args, **kwargs) -> None:
    print("ACC1 SWITCH triggered, state: ", lock.get_state(channel))


@MultiLock.flip_lock
async def my_callback_acc2(channel, lock, state, *args, **kwargs) -> None:
    print("ACC2 SWITCH triggered, state: ", lock.get_state(channel))


@MultiLock.flip_lock
async def my_callback_acc3(channel, lock, state, *args, **kwargs) -> None:
    print("ACC3 SWITCH triggered, state: ", lock.get_state(channel))


if __name__ == '__main__':
    listener(
        my_callback_button,
        my_callback_switch,
        my_callback_acc1,
        my_callback_acc2,
        my_callback_acc3,
    )

