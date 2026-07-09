package com.oocourse.spec3.exceptions;

/**
 * {@code InvalidAgeException} 类用于表示当用户年龄不合法时抛出的异常。
 * 该异常类包含一个整型参数 {@code age}，表示触发异常的具体用户年龄。
 *
 * <p>异常统计信息的格式为：ia-{@code x}, {@code age}，其中 {@code x} 为此类异常发生的总次数 </p>
 */

public class InvalidAgeException extends Exception {
    private static int count = 0;
    private final int age;

    /**
     * 构造一个新的 {@code InvalidAgeException} 实例。
     *
     * @param age 触发异常的用户年龄
     */
    public InvalidAgeException(int age) {
        this.age = age;
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：ia-{@code x}, {@code age}，其中 {@code x} 为此类异常发生的总次数
     */
    public void print() {
        System.out.println("ia-" + count + ", " + age);
    }
}