package com.oocourse.spec3.exceptions;

/**
 * {@code InvalidRankException} 类用于表示当推荐的 up 名次不合法时抛出的异常。
 * 该异常类包含一个整型参数 {@code rank}，表示触发异常的具体个数。
 *
 * <p>异常统计信息的格式为：ir-{@code x}, {@code rank}，其中 {@code x} 为此类异常发生的总次数 </p>
 */

public class InvalidRankException extends Exception {
    private static int count = 0;
    private final int rank;

    /**
     * 构造一个新的 {@code InvalidRankException} 实例。
     *
     * @param rank 触发异常的名次
     */
    public InvalidRankException(int rank) {
        this.rank = rank;
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：ir{@code x}, {@code rank}，其中 {@code x} 为此类异常发生的总次数
     */
    public void print() {
        System.out.println("ir-" + count + ", " + rank);
    }
}