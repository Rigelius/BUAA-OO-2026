package com.oocourse.spec2.exceptions;

/**
 * {@code InvalidCoinsException} 类用于表示当用户投币数不合法时抛出的异常。
 * 该异常类包含一个整型参数 {@code coins}，表示触发异常的具体投币数。
 *
 * <p>异常统计信息的格式为：ivc-{@code x}, {@code age}，其中 {@code x} 为此类异常发生的总次数 </p>
 */

public class InvalidCoinsException extends MyException {
    private static int count = 0;
    private final int coins;

    /**
     * 构造一个新的 {@code InvalidCoinsException} 实例。
     *
     * @param coins 触发异常的投币数
     */
    public InvalidCoinsException(int coins) {
        this.coins = coins;
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：ivc-{@code x}, {@code age}，其中 {@code x} 为此类异常发生的总次数
     */
    public void print() {
        System.out.println("ivc-" + count + ", " + coins);
    }
}