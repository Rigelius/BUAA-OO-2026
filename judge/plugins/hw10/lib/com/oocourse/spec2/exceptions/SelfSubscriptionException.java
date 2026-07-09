package com.oocourse.spec2.exceptions;

/**
 * {@code SelfSubscriptionException} 类用于表示当用户尝试关注自己时抛出的异常。
 * 该异常类包含一个整型参数 {@code id}，表示触发异常的具体用户 ID。
 *
 * <p>异常统计信息的格式为：ss-{@code x}, {@code id}-{@code y}，其中 {@code x} 为此类异常发生的总次数，
 * {@code y} 为该 {@code id} 触发此类异常的次数。</p>
 */
public class SelfSubscriptionException extends MyException {
    private static final ErrorCount errorCount = new ErrorCount();
    private final int id;

    /**
     * 构造一个新的 {@code SelfSubscriptionException} 实例。
     *
     * @param id 触发异常的用户 ID
     */
    public SelfSubscriptionException(int id) {
        this.id = id;
        errorCount.putError(id);
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：ss-{@code x}, {@code id}-{@code y}，其中 {@code x} 为此类异常发生的总次数，
     * {@code y} 为该 {@code id} 触发此类异常的次数。
     */
    public void print() {
        System.out.println("ss-" + errorCount.getCount() + ", "
                + id + "-" + errorCount.getIdCount(id));
    }
}
