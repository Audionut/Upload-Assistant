import asyncio
import psutil
import threading
import multiprocessing
import sys
import os
import subprocess
import re
from src.console import console
from concurrent.futures import ThreadPoolExecutor
if os.name == "posix":
    import termios

running_subprocesses = set()
thread_executor: ThreadPoolExecutor = None
IS_MACOS = sys.platform == 'darwin'


async def cleanup():
    """Ensure all running tasks, threads, and subprocesses are properly cleaned up before exiting."""
    # console.print("[yellow]Cleaning up tasks before exiting...[/yellow]")

    # Step 1: Shutdown ThreadPoolExecutor **before checking for threads**
    global thread_executor
    if thread_executor:
        # console.print("[yellow]Shutting down thread pool executor...[/yellow]")
        thread_executor.shutdown(wait=True)  # Ensure threads terminate before proceeding
        thread_executor = None  # Remove reference

    # 🔹 Step 1: Stop the monitoring thread safely
    # if not stop_monitoring.is_set():
    #    console.print("[yellow]Stopping thread monitor...[/yellow]")
    #    stop_monitoring.set()  # Tell monitoring thread to stop

    # 🔹 Step 2: Wait for the monitoring thread to exit completely
    # if monitor_thread and monitor_thread.is_alive():
    #    console.print("[yellow]Waiting for monitoring thread to exit...[/yellow]")
    #    monitor_thread.join(timeout=3)  # Ensure complete shutdown
    #    if monitor_thread.is_alive():
    #        console.print("[red]Warning: Monitoring thread did not exit in time.[/red]")

    # 🔹 Step 3: Terminate all tracked subprocesses
    while running_subprocesses:
        proc = running_subprocesses.pop()
        if proc.returncode is None:  # If still running
            # console.print(f"[yellow]Terminating subprocess {proc.pid}...[/yellow]")
            proc.terminate()  # Send SIGTERM first
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)  # Wait for process to exit
            except asyncio.TimeoutError:
                # console.print(f"[red]Subprocess {proc.pid} did not exit in time, force killing.[/red]")
                proc.kill()  # Force kill if it doesn't exit

        # 🔹 Close process streams safely
        for stream in (proc.stdout, proc.stderr, proc.stdin):
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

    # 🔹 Step 4: Ensure subprocess transport cleanup
    await asyncio.sleep(0.1)

    # 🔹 Step 5: Cancel all running asyncio tasks **gracefully**
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    # console.print(f"[yellow]Cancelling {len(tasks)} remaining tasks...[/yellow]")

    for task in tasks:
        task.cancel()

    # Stage 1: Give tasks a moment to cancel themselves
    await asyncio.sleep(0.1)

    # Stage 2: Gather tasks with exception handling
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            console.print(f"[red]Error during cleanup: {result}[/red]")

    # 🔹 Step 6: Kill all remaining threads and orphaned processes
    kill_all_threads()

    if IS_MACOS:
        try:
            # Ensure any multiprocessing resources are properly released
            multiprocessing.resource_tracker._resource_tracker = None
        except Exception:
            console.print("[red]Error releasing multiprocessing resources.[/red]")
            pass

    # console.print("[green]Cleanup completed. Exiting safely.[/green]")


def kill_all_threads():
    """Forcefully kill any lingering threads and subprocesses before exit."""
    # console.print("[yellow]Checking for remaining background threads...[/yellow]")

    # 🔹 Kill any lingering subprocesses
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)

        for child in children:
            # console.print(f"[yellow]Terminating process {child.pid}...[/yellow]")
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # Wait for a short time for processes to terminate
        if not IS_MACOS:
            _, still_alive = psutil.wait_procs(children, timeout=3)
            for child in still_alive:
                # console.print(f"[red]Force killing stubborn process: {child.pid}[/red]")
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
    except Exception as e:
        console.print(f"[red]Error killing processes: {e}[/red]")
        pass

    # 🔹 For macOS, specifically check and terminate any multiprocessing processes
    if IS_MACOS and hasattr(multiprocessing, 'active_children'):
        for child in multiprocessing.active_children():
            try:
                child.terminate()
                child.join(1)  # Wait 1 second for it to terminate
            except Exception:
                pass

    # 🔹 Remove references to completed threads
    try:
        for thread in threading.enumerate():
            if thread != threading.current_thread() and not thread.is_alive():
                try:
                    if hasattr(thread, '_delete'):
                        thread._delete()
                except Exception:
                    pass
    except Exception as e:
        console.print(f"[red]Error cleaning up threads: {e}[/red]")
        pass

    # 🔹 Print remaining active threads
    # active_threads = [t for t in threading.enumerate()]
    # console.print(f"[bold yellow]Remaining active threads:[/bold yellow] {len(active_threads)}")
    # for t in active_threads:
    #    console.print(f"  - {t.name} (Alive: {t.is_alive()})")

    # console.print("[green]Thread cleanup completed.[/green]")


# Wrapped "erase key check and save" in tty check so that Python won't complain if UA is called by a script
if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty() and not sys.stdin.closed:
    try:
        output = subprocess.check_output(['stty', '-a']).decode()
        erase_key = re.search(r' erase = (\S+);', output).group(1)
    except (IOError, OSError):
        pass


def reset_terminal():
    """Reset the terminal while allowing the script to continue running (Linux/macOS only)."""
    if os.name != "posix":
        return

    try:
        if not sys.stderr.closed:
            sys.stderr.flush()

        if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty() and not sys.stdin.closed:
            try:
                subprocess.run(["stty", "sane"], check=False)
                subprocess.run(["stty", "erase", erase_key], check=False)  # explicitly restore backspace character to original value
                if hasattr(termios, 'tcflush'):
                    termios.tcflush(sys.stdin.fileno(), termios.TCIOFLUSH)
                subprocess.run(["stty", "-ixon"], check=False)
            except (IOError, OSError):
                pass

        if not sys.stdout.closed:
            try:
                sys.stdout.write("\033[0m")
                sys.stdout.flush()
                sys.stdout.write("\033[?25h")
                sys.stdout.flush()
            except (IOError, ValueError):
                pass

        # Kill background jobs
        try:
            os.system("jobs -p | xargs -r kill 2>/dev/null")
        except Exception:
            pass

        if not sys.stderr.closed:
            sys.stderr.flush()

    except Exception as e:
        try:
            if not sys.stderr.closed:
                sys.stderr.write(f"Error during terminal reset: {e}\n")
                sys.stderr.flush()
        except Exception:
            pass  # At this point we can't do much more
