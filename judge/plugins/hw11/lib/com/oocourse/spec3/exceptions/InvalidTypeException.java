package com.oocourse.spec3.exceptions;

/**
 * {@code InvalidTypeException} 类用于表示当视频类型不合法时抛出的异常。
 * 该异常类包含一个字符串型参数 {@code type}，表示触发异常的具体类型。
 *
 * <p>异常统计信息的格式为：it-{@code x}，其中 {@code x} 为此类异常发生的总次数 </p>
 */

public class InvalidTypeException extends Exception {
    private static int count = 0;
    private final String type;

    /**
     * 构造一个新的 {@code InvalidTypeException} 实例。
     *
     * @param type 触发异常的用户年龄
     */
    public InvalidTypeException(String type) {
        this.type = type;
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：it-{@code x}, {@code type}，其中 {@code x} 为此类异常发生的总次数
     */
    public void print() {
        System.out.println("it-" + count + ", "  + type);
    }
}