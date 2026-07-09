package com.oocourse.spec2.exceptions;

/**
 * {@code InvalidCommentException} 类用于表示当用户评论为空时抛出的异常。
 *
 * <p>异常统计信息的格式为：ict-{@code x}，其中 {@code x} 为此类异常发生的总次数 </p>
 */

public class InvalidCommentException extends MyException {
    private static int count = 0;
    /**
     * 构造一个新的 {@code InvalidCommentException} 实例。
     */
    public InvalidCommentException() {
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：ict-{@code x}，其中 {@code x} 为此类异常发生的总次数
     */
    public void print() {
        System.out.println("ict-" + count);
    }
}
