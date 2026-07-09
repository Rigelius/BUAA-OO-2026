package com.oocourse.spec3.main;

import java.text.SimpleDateFormat;
import java.util.Date;

public class ErrorStatisticsHandler {
    private static final String FILE_PATH = "ErrorStatistics.txt";
    
    /**
     * 记录异常信息到标准错误流 (System.err)
     * @param e 捕获到的异常
     * @param rawCommand 原始输入的指令字符串
     */
    public static void logError(Exception e, String rawCommand) {
        // 1. 从堆栈中提取 Runner 中的函数名 (保持原有逻辑不变)
        String runnerMethodName = extractRunnerMethod(e);
        
        // 2. 构造输出内容
        String timestamp = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date());
        String logContent = String.format("[%s] Function: %s | Exception: %s | Command: %s",
                timestamp,
                runnerMethodName,
                e.getClass().getSimpleName(),
                rawCommand
        );
        
        // 3. 修改点：直接输出到标准错误流，不再写入文件
        System.err.println(logContent);
    }
    
    /**
     * 遍历异常堆栈，寻找第一个属于 Runner 类的非 run 方法
     * (逻辑保持不变)
     */
    private static String extractRunnerMethod(Exception e) {
        StackTraceElement[] stackTrace = e.getStackTrace();
        for (StackTraceElement element : stackTrace) {
            String className = element.getClassName();
            String methodName = element.getMethodName();
            
            // 寻找 Runner 类中非 run 的方法
            if (className.endsWith("Runner") && !methodName.equals("run")) {
                return methodName;
            }
        }
        // 如果无法定位具体方法，尝试返回栈顶的 Runner 方法
        for (StackTraceElement element : stackTrace) {
            if (element.getClassName().endsWith("Runner")) {
                return element.getMethodName();
            }
        }
        return "UnknownContext";
    }
}