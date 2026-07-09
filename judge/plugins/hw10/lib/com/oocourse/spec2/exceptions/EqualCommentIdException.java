package com.oocourse.spec2.exceptions;

/**
 * {@code EqualCommentIdException} 类用于表示当不满足评论 ID 唯一性要求时抛出的异常。
 * 该异常类包含一个整型参数 {@code id}，表示触发异常的具体评论 ID。
 *
 * <p>异常统计信息的格式为：eci-{@code x}, {@code id}-{@code y}，其中 {@code x} 为此类异常发生的总次数，
 * {@code y} 为该 {@code id} 触发此类异常的次数。</p>
 */
public class EqualCommentIdException extends MyException {
    private static final ErrorCount errorCount = new ErrorCount();
    private final int id;

    /**
     * 构造一个新的 {@code EqualCommentIdException} 实例。
     *
     * @param id 触发异常的评论 ID
     */
    public EqualCommentIdException(int id) {
        this.id = id;
        errorCount.putError(id);
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：eci-{@code x}, {@code id}-{@code y}，其中 {@code x} 为此类异常发生的总次数，
     * {@code y} 为该 {@code id} 触发此类异常的次数。
     */
    public void print() {
        System.out.println("eci-" + errorCount.getCount() + ", "
                + id + "-" + errorCount.getIdCount(id));
    }
}
