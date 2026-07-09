package com.oocourse.spec2.main;

public interface VideoInterface {

    /*@ public instance model int id;
      @ public instance model int uploaderId;
      @ public instance model String type;
      @ public instance model int playCount;
      @ public instance model int likes;
      @ public instance model int forwardCount;
      @ public instance model int coins;
      @ public instance model non_null int[] commentIds;
      @ public instance model non_null String[] commentContents;
      @*/

    /*@ invariant commentIds.length == commentContents.length &&
      @  (\forall int i,j; 0 <= i && i < j && j < commentIds.length;
      @     commentIds[i] != commentIds[j])
      @*/

    // ensures \result == id;
    public /*@ pure @*/ int getId();

    // ensures \result == uploaderId;
    public /*@ pure @*/ int getUploaderId();

    // ensures \result == type;
    public /*@ pure @*/ String getType(); // 新增
    
    // ensures \result == playCount;
    public /*@ pure @*/ int getPlayCount();

    // ensures \result == likeCount;
    public /*@ pure @*/ int getLikes();

    // ensures \result == forwardCount;
    public /*@ pure @*/ int getForwardCount();

    // ensures \result == coins;
    public /*@ pure @*/ int getCoins();

    // ensures \result == playCount * 1 + likes * 1.5 + forwardCount * 2.0 + coins * 2.5;
    public /*@ pure @*/ double getHeat();

    //@ ensures \result == (\exists int i; 0 <= i && i < commentIds.length; commentIds[i] == id);
    public /*@ pure @*/ boolean containsComment(int id);

    /*@ public normal_behavior
      @ requires obj != null && obj instanceof VideoInterface;
      @ assignable \nothing;
      @ ensures \result == (((VideoInterface) obj).getId() == id);
      @ also
      @ public normal_behavior
      @ requires obj == null || !(obj instanceof VideoInterface);
      @ assignable \nothing;
      @ ensures \result == false;
      @*/
    public /*@ pure @*/ boolean equals(Object obj);

}