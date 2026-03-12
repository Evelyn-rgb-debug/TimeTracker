# Time Tracker :)

A lightweight desktop time-tracking application for Windows, built with **Python** and **PySide6**.

This app combines a timer, calendar, task logging, planning, and work-summary statistics in a single glass-style interface. It is designed for personal daily tracking with quick start/stop logging, editable records, calendar-based review, and system tray support.

---

## 1. How to Run
#Method 1
Download the TimeTracker.exe file from the dist folder and double-click to install.

#Method 2
Download all file in this project(except build folder, dist folder, TimeTracker.spec). The program's source files may be unstable on different computers, but they facilitate secondary development by users.
1. Open this project folder
2. Double-click: install_requirements.bat
3. After the dependencies are installed, launch the app by double-clicking: start_time_tracker.bat

The program also includes calendar-based review and planning features. Users can browse records in month, week, and day views, inspect tasks for a selected date, edit or delete existing items, and create planned tasks alongside completed logs. In addition, the app provides statistics and work-summary views that aggregate recorded time by category and present the results visually, making it easier to review daily, weekly, or monthly workload. The interface is supported by system tray integration, local persistence, saved window state, and Windows auto-start behavior, so the app can remain lightweight in daily use while still functioning like a full desktop utility.

From a technical perspective, the application is mainly implemented in `main.py`, which acts as the central controller for timer behavior, database operations, UI updates, calendar rendering, statistics, system tray support, and startup logic. The project is built in Python, uses PySide6 as the GUI framework, and stores user data in SQLite. Its internal structure is relatively straightforward: helper functions manage paths and Windows-specific behavior, `TrackerDB` handles data persistence, custom Qt widgets render the interface, and `MainWindow` coordinates the main workflow and interactions between components. The supporting files in the repository serve simple roles: `install_requirements.bat` installs the dependencies listed in `requirements.txt`, `start_time_tracker.bat` launches the application normally, `start_time_tracker_debug.bat` is for debugging, `start_hidden.vbs` is used for hidden/background startup behavior on Windows, and `icon.png` provides the app icon.


# Time Tracker :)中文版
（欢迎关注小红书账号：1000024854）
一款轻量级的 Windows 桌面时间追踪应用程序，使用 **Python** 和 **PySide6** 构建。
这款应用将计时器、日历、任务日志、计划和工作总结统计功能整合在一个简洁的玻璃面板界面中。它专为个人日常时间追踪而设计，支持快速开始/停止记录、可编辑记录、基于日历的回顾以及系统托盘支持。
---
如何运行
方法1（推荐）：
从 dist 文件夹下载 TimeTracker.exe 文件，然后双击安装。

方法2：
下载此项目中的所有文件（build 文件夹、dist 文件夹和 TimeTracker.spec 文件除外）。程序源文件在不同的计算机上可能不稳定，但方便用户进行二次开发。
1. 打开此项目文件夹
2. 双击：install_requirements.bat
3. 安装依赖项后，双击启动应用程序：start_time_tracker.bat

该程序还包含基于日历的回顾和计划功能。用户可以按月、周和日浏览记录，查看选定日期的任务，编辑或删除现有项目，并在已完成的日志旁边创建计划任务。此外，该应用提供统计信息和工作总结视图，按类别汇总记录的时间并以可视化的方式呈现结果，方便用户查看每日、每周或每月的工作量。该界面支持系统托盘集成、本地持久化、保存窗口状态以及 Windows 自动启动功能，因此在日常使用中保持轻量级，同时又具备完整的桌面实用程序功能。

从技术角度来看，该应用主要在 `main.py` 中实现，它作为中央控制器，负责计时器行为、数据库操作、UI 更新、日历渲染、统计信息、系统托盘支持和启动逻辑。该项目使用 Python 编写，采用 PySide6 作为 GUI 框架，并将用户数据存储在 SQLite 数据库中。其内部结构相对简单：辅助函数管理路径和 Windows 特有的行为，`TrackerDB` 处理数据持久化，自定义 Qt 小部件渲染界面，`MainWindow` 协调主要工作流程和组件之间的交互。存储库中的支持文件扮演着简单的角色：`install_requirements.bat` 安装 `requirements.txt` 中列出的依赖项，`start_time_tracker.bat` 正常启动应用程序，`start_time_tracker_debug.bat` 用于调试，`start_hidden.vbs` 用于 Windows 上的隐藏/后台启动行为，`icon.png` 提供应用程序图标。
