package com.oocourse.spec3.exceptions;

/**
 * {@code NoUserException} 类用于表示网络中没有用户时抛出的异常。
 *
 * <p>异常统计信息的格式为：nu-{@code x},其中 {@code x} 为此类异常发生的总次数，
 */
public class NoUserException extends MyException {
    private static int count = 0;
    
    /**
     * 构造一个新的 {@code NoUserException} 实例。
     */
    public NoUserException() {
        count++;
    }
    
    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：nu-{@code x}其中 {@code x} 为此类异常发生的总次数，
     */
    public void print() {
        System.out.println("nu-" + count);
    }
}
