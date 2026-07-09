package com.oocourse.spec1.main;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;

public class ErrorStatisticsHandler {
    private static final String FILE_PATH = "ErrorStatistics.txt";
    
    /**
     * 记录异常信息
     * @param e 捕获到的异常
     * @param rawCommand 原始输入的指令字符串
     */
    public static void logError(Exception e, String rawCommand) {
        String runnerMethodName = extractRunnerMethod(e);

        String timestamp = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date());
        String logContent = String.format("[%s] Function: %s | Exception: %s | Command: %s",
                timestamp,
                runnerMethodName,
                e.getClass().getSimpleName(),
                rawCommand
        );

        System.err.println(logContent);
    }
    
    /**
     * 遍历异常堆栈，寻找第一个属于 Runner 类的非 run 方法
     * 如果没找到，则返回 "Unknown" 或栈顶方法
     */
    private static String extractRunnerMethod(Exception e) {
        StackTraceElement[] stackTrace = e.getStackTrace();
        for (StackTraceElement element : stackTrace) {
            String className = element.getClassName();
            String methodName = element.getMethodName();

            if (className.endsWith("Runner") && !methodName.equals("run")) {
                return methodName;
            }
        }

        for (StackTraceElement element : stackTrace) {
            if (element.getClassName().endsWith("Runner")) {
                return element.getMethodName();
            }
        }
        return "UnknownContext";
    }
}