import asyncio

async def task1():
    await asyncio.sleep(2)
    return "Task 1 finished"

async def task2():
    await asyncio.sleep(3)
    return "Task 2 finished"

async def main():
    tasks = [task1(), task2()]
    
    done, pending = await asyncio.wait(tasks, timeout=2.5)
    
    for task in done:
        print(task.result())
    
    if pending:
        print("Some tasks didn't finish in time!")

asyncio.run(main())
